"""Syncs of docs/concepts/syncs.md, section "Running a job". No sync retries a job."""
from __future__ import annotations

from dataclasses import dataclass

from app import flags
from app.adapters.ports import Call, Open, Set, Step
from app.modules.actionpolicy_v1 import Accept, Deny, Reject
from app.modules.jobqueue_v1 import JobId, JobState
from app.modules.verification_v1 import Match, Mismatch

from .world import World

POPUP_CLOSERS = ("close_picker",)


@dataclass(frozen=True)
class Halt:
    reason: str


@dataclass
class Cursor:
    """Where the viewer is, as far as the worker knows; the viewer port has no way to ask."""

    screen: str = "HomeScreen"
    parent: str | None = None
    last_fn: str | None = None
    saved: bool = False


def _allow_save(payload: dict) -> bool:
    return bool(payload["save"]) and flags.is_enabled("save")


def run_next_job(world: World) -> JobId | None:
    taken = world.queue.take()
    if taken is None:
        return None
    job, payload = taken
    world.emit("RunNextJob", "job taken", job=job, save=_allow_save(payload))
    try:
        cursor = Cursor()
        halt = _execute(world, world.recipe.steps(payload), cursor, _allow_save(payload))
        if halt is not None:
            _halt(world, job, halt)
        elif cursor.saved:
            saved_job_is_read_back(world, job, payload, cursor)
        else:
            world.erp.reset()
            _finish(world, "RunNextJob", job, JobState.DONE, "dry run")
    except Exception as error:
        adapter_error_finishes_job(world, job, error)
    return job


def saved_job_is_read_back(world: World, job: JobId, payload: dict, cursor: Cursor | None = None) -> None:
    if cursor is None:
        cursor = Cursor()
    halt = _execute(world, world.recipe.read_back_steps(job), cursor, _allow_save(payload))
    if halt is not None:
        _halt(world, job, halt)
        return
    document = world.erp.read_back(world.recipe.read_back_ref(job))
    actual = {"header": dict(document.header), "lines": [dict(line) for line in document.lines]}
    expected = {
        "header": {"ref": job},
        "lines": [
            {"code": line["code"], "qty": line["qty"], **_price_if_any(line)} for line in payload["lines"]
        ],
    }
    world.emit("SavedJobIsReadBack", "document read back", job=job, lines=len(actual["lines"]))
    verification_finishes_job(world, job, world.verification.compare(job, expected, actual))


def _price_if_any(line: dict) -> dict:
    return {"price": line["price"]} if line.get("price") is not None else {}


def verification_finishes_job(world: World, job: JobId, result: Match | Mismatch) -> None:
    if isinstance(result, Match):
        _finish(world, "VerificationFinishesJob", job, JobState.DONE, "saved and verified")
    else:
        _finish(world, "VerificationFinishesJob", job, JobState.NEEDS_HUMAN, "; ".join(result.reasons))


def adapter_error_finishes_job(world: World, job: JobId, error: Exception) -> None:
    try:
        world.erp.reset()
    except Exception:
        pass
    _finish(world, "AdapterErrorFinishesJob", job, JobState.FAILED, f"{type(error).__name__}: {error}")


def _finish(world: World, sync: str, job: JobId, state: JobState, detail: str) -> None:
    world.queue.finish(job, state, detail)
    world.emit(sync, "job finished", job=job, state=state.value, detail=detail)


def _halt(world: World, job: JobId, halt: Halt) -> None:
    world.erp.reset()
    _finish(world, "RunNextJob", job, JobState.NEEDS_HUMAN, halt.reason)


def _execute(world: World, steps: list[Step], cursor: Cursor, allow_save: bool) -> Halt | None:
    for step in steps:
        if isinstance(step, Set):
            world.erp.set_value(step.path, step.value)
            continue
        if isinstance(step, Open):
            verdict = world.policy.check_screen(step.screen, cursor.screen, cursor.last_fn)
            if isinstance(verdict, Deny):
                world.emit("RunNextJob", "denied", step=f"open {step.screen}", reason=verdict.reason)
                return Halt(verdict.reason)
            world.erp.open_screen(step.screen)
            world.emit("RunNextJob", "opened", screen=step.screen)
            cursor.screen, cursor.parent, cursor.last_fn = step.screen, None, None
            saving, during = False, None
        else:
            verdict = world.policy.check_call(cursor.screen, step.fn, allow_save, step.is_save)
            if isinstance(verdict, Deny):
                world.emit("RunNextJob", "denied", step=f"call {step.fn}", reason=verdict.reason)
                return Halt(verdict.reason)
            world.erp.call(step.fn)
            world.emit("RunNextJob", "called", screen=cursor.screen, fn=step.fn, saving=step.is_save)
            _follow(world, cursor, step.fn)
            saving, during = step.is_save, step.fn
        halt = _drain_dialogs(world, saving, during)
        if halt is not None:
            return halt
        if isinstance(step, Call) and step.is_save:
            cursor.saved = True
    return None


def _follow(world: World, cursor: Cursor, fn: str) -> None:
    popups = world.policy.rules()["popups"]
    opened = next((n for n, p in popups.items() if p["opener"] == fn and p["parent"] == cursor.screen), None)
    if opened is not None:
        cursor.parent, cursor.screen = cursor.screen, opened
    elif cursor.parent is not None and fn in POPUP_CLOSERS:
        cursor.screen, cursor.parent = cursor.parent, None
    cursor.last_fn = fn


def _drain_dialogs(world: World, saving: bool, during: str | None) -> Halt | None:
    while (text := world.erp.pending_dialog()) is not None:
        verdict = world.policy.classify_dialog(text, saving, during=during)
        if isinstance(verdict, (Accept, Reject)):
            accept = isinstance(verdict, Accept)
            world.erp.answer_dialog(accept)
            world.emit("RunNextJob", "dialog accepted" if accept else "dialog rejected", text=text)
        else:
            world.emit("RunNextJob", "dialog unknown, stopping", text=text, reason=verdict.reason)
            return Halt(verdict.reason)
    return None
