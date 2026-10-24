"""Syncs of docs/concepts/syncs.md, sections "Running a job", "Interrupted jobs and the save journal" and
"Changing a saved document". No sync retries a job."""
from __future__ import annotations

from dataclasses import dataclass

from app import flags, settings
from app.adapters.ports import Call, Document, Open, Set, Step
from app.modules import revision_v1 as revision
from app.modules.actionpolicy_v1 import Accept, Deny, Reject
from app.modules.jobqueue_v1 import JobId, JobState
from app.modules.verification_v1 import Match
from app.modules.verification_v2 import Found, Many, NotFound
from app.modules.verification_v2 import Match as MatchV2

from .world import World

POPUP_CLOSERS = ("close_picker",)
REMOVAL_FUNCTION = "remove_line"


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
    edit_code: str | None = None


def _allow_save(payload: dict) -> bool:
    return bool(payload["save"]) and flags.is_enabled("save")


def _v2() -> bool:
    return flags.is_enabled("verification_v2")


def run_next_job(world: World) -> JobId | None:
    taken = world.queue.take()
    if taken is None:
        return None
    job, payload = taken
    world.emit("RunNextJob", "job taken", job=job, save=_allow_save(payload), mode=payload.get("mode", "new"))
    try:
        if payload.get("mode") == "edit":
            run_edit_job(world, job, payload)
        else:
            _run_new_job(world, job, payload)
    except Exception as error:
        adapter_error_finishes_job(world, job, error)
    return job


def _run_new_job(world: World, job: JobId, payload: dict) -> None:
    cursor = Cursor()
    known_before: frozenset[str] = frozenset()
    if _allow_save(payload) and _v2():
        halt = _execute(world, job, payload, world.recipe.read_back_steps(job), cursor, False, frozenset())
        if halt is not None:
            _halt(world, job, halt)
            return
        known_before = frozenset(d.header["ref"] for d in world.erp.list_documents())
    halt = _execute(world, job, payload, world.recipe.steps(payload), cursor, _allow_save(payload), known_before)
    if halt is not None:
        _halt(world, job, halt)
    elif cursor.saved:
        saved_job_is_read_back(world, job, payload, cursor)
    else:
        world.erp.reset()
        _finish(world, "RunNextJob", job, JobState.DONE, "dry run")


def recover_interrupted_jobs(world: World) -> list[JobId]:
    """Worker start: a job left running by a worker that died is read back if a save was journaled, never re-typed."""
    recovered = []
    for job in world.queue.list(JobState.RUNNING):
        payload = world.queue.payload(job)
        phase = world.journal.phase(job)
        world.emit("RecoverInterruptedJob", "found running job", job=job, journal=phase or "none")
        try:
            world.erp.reset()
            if phase is None:
                _finish(world, "RecoverInterruptedJob", job, JobState.NEEDS_HUMAN, "interrupted before saving")
            else:
                saved_job_is_read_back(world, job, payload)
        except Exception as error:
            adapter_error_finishes_job(world, job, error)
        recovered.append(job)
    return recovered


def edit_becomes_job(world: World, job_of: JobId, lines: list[dict], edit_job: JobId) -> bool:
    base = world.journal.saved_lines(job_of)
    ref = world.journal.saved_ref(job_of)
    if base is None or ref is None:
        raise ValueError(f"job {job_of!r} has no saved and read-back document to change")
    payload = {"job": edit_job, "mode": "edit", "of": job_of, "ref": ref, "base": base, "lines": lines, "save": True}
    queued = world.queue.enqueue(edit_job, payload)
    world.emit("EditBecomesJob", "edit queued" if queued else "edit refused, id known", job=edit_job, of=job_of, ref=ref)
    return queued


def run_edit_job(world: World, job: JobId, payload: dict) -> None:
    ref = payload["ref"]
    cursor = Cursor()
    halt = _execute(world, job, payload, world.recipe.read_back_steps(job), cursor, False, frozenset())
    if halt is not None:
        _halt(world, job, halt)
        return
    current = _as_dict(world.erp.read_back(ref))
    planned = revision.plan(payload["base"], current if current["lines"] else None, payload["lines"])
    if isinstance(planned, revision.Stop):
        detail = planned.reason + (": " + "; ".join(planned.diffs) if planned.diffs else "")
        world.emit("RunEditJob", "plan stopped", job=job, reason=detail)
        _halt(world, job, Halt(detail))
        return
    world.emit("RunEditJob", "planned", job=job, ops=len(planned.ops))
    mark = len(world.erp.request_log())
    steps = world.recipe.edit_steps(ref, list(planned.ops))
    halt = _execute(world, job, payload, steps, cursor, _allow_save(payload), frozenset())
    if halt is not None:
        _halt(world, job, halt)
        return
    sent = world.erp.request_log()[mark:]
    checked = revision.check_requests(sent, settings.EDIT_UPDATE_REQUEST, set(settings.EDIT_DANGEROUS_REQUESTS))
    world.emit("RunEditJob", "requests checked", job=job, requests=",".join(sent))
    if isinstance(checked, revision.Stop):
        _halt(world, job, Halt(checked.reason))
        return
    saved_job_is_read_back(world, job, payload, cursor)


def saved_job_is_read_back(world: World, job: JobId, payload: dict, cursor: Cursor | None = None) -> None:
    if cursor is None:
        cursor = Cursor()
    halt = _execute(world, job, payload, world.recipe.read_back_steps(job), cursor, False, frozenset())
    if halt is not None:
        _halt(world, job, halt)
        return
    if payload.get("mode") == "edit":
        ref = payload["ref"]
    elif _v2():
        documents = [dict(d.header) for d in world.erp.list_documents()]
        located = world.verification_v2.locate(job, documents, world.journal.known_before(job) or frozenset())
        if isinstance(located, NotFound):
            _halt(world, job, Halt("saved document not found"))
            return
        if isinstance(located, Many):
            _halt(world, job, Halt("several new documents: " + ", ".join(located.refs)))
            return
        assert isinstance(located, Found)
        ref = located.ref
    else:
        ref = world.recipe.read_back_ref(job)
    if world.journal.phase(job) is not None:
        world.journal.mark_read_back(job, ref)
    actual = _as_dict(world.erp.read_back(ref))
    expected = {
        "header": {"ref": ref},
        "lines": [
            {"code": line["code"], "qty": line["qty"], **_price_if_any(line)} for line in payload["lines"]
        ],
    }
    world.emit("SavedJobIsReadBack", "document read back", job=job, ref=ref, lines=len(actual["lines"]))
    verification = world.verification_v2 if _v2() else world.verification
    verification_finishes_job(world, job, verification.compare(job, expected, actual))


def _as_dict(document: Document) -> dict:
    return {"header": dict(document.header), "lines": [dict(line) for line in document.lines]}


def _price_if_any(line: dict) -> dict:
    return {"price": line["price"]} if line.get("price") is not None else {}


def verification_finishes_job(world: World, job: JobId, result) -> None:
    if isinstance(result, (Match, MatchV2)):
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


def _execute(
    world: World,
    job: JobId,
    payload: dict,
    steps: list[Step],
    cursor: Cursor,
    allow_save: bool,
    known_before: frozenset[str],
) -> Halt | None:
    for step in steps:
        if isinstance(step, Set):
            world.erp.set_value(step.path, step.value)
            if step.path == "edit.code":
                cursor.edit_code = step.value
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
            if step.is_save:
                halt = _journal_save(world, job, payload, known_before)
                if halt is not None:
                    return halt
            world.erp.call(step.fn)
            world.emit("RunNextJob", "called", screen=cursor.screen, fn=step.fn, saving=step.is_save)
            _follow(world, cursor, step.fn)
            saving, during = step.is_save, step.fn
        halt = _drain_dialogs(world, cursor, saving, during)
        if halt is not None:
            return halt
        if isinstance(step, Call) and step.is_save:
            cursor.saved = True
    return None


def _journal_save(world: World, job: JobId, payload: dict, known_before: frozenset[str]) -> Halt | None:
    if world.journal.phase(job) is not None:
        world.emit("SaveIsJournaled", "save already attempted", job=job)
        return Halt("save already attempted")
    world.journal.mark_saving(job, payload["lines"], known_before)
    world.emit("SaveIsJournaled", "journaled before save", job=job)
    return None


def _follow(world: World, cursor: Cursor, fn: str) -> None:
    popups = world.policy.rules()["popups"]
    opened = next((n for n, p in popups.items() if p["opener"] == fn and p["parent"] == cursor.screen), None)
    if opened is not None:
        cursor.parent, cursor.screen = cursor.screen, opened
    elif cursor.parent is not None and fn in POPUP_CLOSERS:
        cursor.screen, cursor.parent = cursor.parent, None
    cursor.last_fn = fn


def _drain_dialogs(world: World, cursor: Cursor, saving: bool, during: str | None) -> Halt | None:
    while (text := world.erp.pending_dialog()) is not None:
        verdict = world.policy.classify_dialog(text, saving, during=during)
        if isinstance(verdict, Accept) and during == REMOVAL_FUNCTION:
            named = world.recipe.item_in_dialog(text)
            if not revision.may_confirm_removal(named, cursor.edit_code):
                world.erp.answer_dialog(False)
                world.emit("RunEditJob", "removal names another item", text=text, removing=cursor.edit_code)
                return Halt(f"removal confirmation names {named}, removing {cursor.edit_code}")
        if isinstance(verdict, (Accept, Reject)):
            accept = isinstance(verdict, Accept)
            world.erp.answer_dialog(accept)
            world.emit("RunNextJob", "dialog accepted" if accept else "dialog rejected", text=text)
        else:
            world.emit("RunNextJob", "dialog unknown, stopping", text=text, reason=verdict.reason)
            return Halt(verdict.reason)
    return None
