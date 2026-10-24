"""The scenarios of `python -m demo`. Each one narrates, checks its own expectations and returns an Outcome."""
from __future__ import annotations

import os
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal

from app import adapters
from app.adapters import FakeErpViewer, flicker
from app.adapters.ports import Document, PhoneEvent
from app.modules.jobqueue_v1 import JobState
from app.modules.quote_v1 import QuoteSent
from app.syncs import (
    Event,
    World,
    build_world,
    hang_up_ends_call,
    operator_adds_catalog_line,
    operator_sets_price,
    poll_phone,
    poll_screen,
    run_next_job,
    sent_quote_becomes_job,
)

from demo.misbehaving import RecipeThatPrints, RecipeThatSavesAnyway, ViewerWithStopButton

T0 = datetime(2026, 10, 24, 9, 0, 0)
NUMBER = "555-0142"
IDENTIFIER = "K7Q2M9X4"
UNKNOWN_DIALOG = "Server is restarting in 5 minutes."


@dataclass
class Outcome:
    number: int
    title: str
    state: str
    expected: str
    proves: str
    failures: list[str]

    @property
    def ok(self) -> bool:
        return not self.failures and self.state == self.expected


@contextmanager
def save_flag(on: bool) -> Iterator[None]:
    name = "LEA_FLAG_SAVE"
    before = os.environ.get(name)
    if on:
        os.environ[name] = "1"
    else:
        os.environ.pop(name, None)
    try:
        yield
    finally:
        if before is None:
            os.environ.pop(name, None)
        else:
            os.environ[name] = before


def _value(value: object) -> str:
    if isinstance(value, datetime):
        return value.strftime("%H:%M:%S")
    return str(value)


def format_event(event: Event) -> str:
    extra = ", ".join(f"{key}={_value(value)}" for key, value in event.data.items())
    return f"[{event.sync}] {event.what}" + (f" ({extra})" if extra else "")


def document_text(document: Document | None) -> str:
    if document is None:
        return "nothing"
    parts = [
        f"{line['code']} x{line['qty']} " + (f"@ {line['price']}" if line.get("price") else "(ERP price)")
        for line in document.lines
    ]
    return f"{document.header.get('ref')}: " + ("; ".join(parts) if parts else "no lines")


def job_line(world: World, job: str) -> tuple[str, str]:
    status = world.queue.status(job)
    detail = f" ({status.detail})" if status.detail else ""
    return status.state.value, f"{job} = {status.state.value}{detail}"


class Scenario:
    def __init__(self, number: int, title: str) -> None:
        self.number = number
        self.title = title
        self.failures: list[str] = []
        self._seen: dict[int, int] = {}
        print()
        print(f"=== Scenario {number}: {title} ===")

    def say(self, text: str) -> None:
        print(f"  {text}")

    def show(self, world: World) -> None:
        start = self._seen.get(id(world), 0)
        for event in world.log[start:]:
            print(f"    {format_event(event)}")
        self._seen[id(world)] = len(world.log)

    def expect(self, ok: bool, text: str) -> None:
        print(f"  [{'ok' if ok else 'FAIL'}] {text}")
        if not ok:
            self.failures.append(text)

    def end(self, verdict: str, final: str, state: str, expected: str, proves: str) -> Outcome:
        print(f"  verdict: {verdict}")
        print(f"  final job state: {final}")
        return Outcome(self.number, self.title, state, expected, proves, self.failures)


def send_quote(world: World, scenario: Scenario, save: bool, price: bool = True) -> str:
    quote = world.quotes.open()
    first, _second = operator_adds_catalog_line(world, quote, IDENTIFIER, qty=2)
    if price:
        operator_sets_price(world, quote, first, Decimal("12.50"))
    sent_quote_becomes_job(world, quote, request_save=save)
    scenario.show(world)
    return quote


def run_once(world: World, scenario: Scenario) -> str:
    job = run_next_job(world)
    scenario.show(world)
    assert job is not None
    return job


def scenario_dry_run() -> Outcome:
    s = Scenario(1, "Dry run (ring, screen reading, quote, job; flag SAVE off)")
    with save_flag(False):
        phone = adapters.make_phone([PhoneEvent("ring", NUMBER, T0)])
        screen = adapters.make_screen(flicker(IDENTIFIER, T0 + timedelta(seconds=4), timedelta(seconds=1)))
        world = build_world(phone=phone, screen=screen)

        s.say("The phone rings.")
        poll_phone(world)
        s.show(world)

        s.say("The screen is still loading and flickers: five readings, one second apart.")
        results = poll_screen(world)
        s.show(world)
        names = [type(result).__name__ for result in results]
        s.expect(names == ["Pending", "Pending", "Pending", "Confirmed", "Repeated"], f"readings gave {names}")
        s.expect(world.sighting.last_confirmed(IDENTIFIER) == T0 + timedelta(seconds=7), "confirmed once, at 09:00:07")

        s.say("The caller hangs up 90 seconds after the ring.")
        hang_up_ends_call(world, PhoneEvent("hang_up", NUMBER, T0 + timedelta(seconds=90)))
        s.show(world)
        (call,) = world.calls.recent()
        s.expect(call.items == (IDENTIFIER,), f"call {call.call} from {call.number} carries {call.items}")

        s.say("The operator adds the catalog lines, sets one price, and sends the quote asking to save.")
        quote = send_quote(world, s, save=True)
        s.say("The worker takes the job.")
        job = run_once(world, s)

    state, final = job_line(world, job)
    s.expect(world.erp.documents == {}, "the ERP holds nothing")
    s.expect(world.erp.reset_count == 1, "the viewer was reset once, nothing was saved")
    s.expect(job == quote and state == "done", "the job is done")
    return s.end(
        "saving was requested but flag SAVE is off, so the job was a dry run",
        final,
        state,
        "done",
        "dry run is the default; the flag is the site-level lock",
    )


def scenario_save_and_verify() -> Outcome:
    s = Scenario(2, "Save and verify (flag SAVE on)")
    with save_flag(True):
        world = build_world()
        send_quote(world, s, save=True)
        s.say("The quote is sent asking to save; the flag is on, so the job may save.")
        job = run_once(world, s)

    state, final = job_line(world, job)
    s.say(f"The fake ERP now holds {document_text(world.erp.documents.get(job))}")
    s.expect(state == "done", "read back matched what was typed")
    s.expect(world.erp.dangerous_calls == [], "no dangerous function was called")
    return s.end(
        "saved, read back through allowed screens, and the two sides match",
        final,
        state,
        "done",
        "both locks open: the dialogs are accepted and the result is verified",
    )


def scenario_unknown_dialog() -> Outcome:
    s = Scenario(3, "A dialog nobody knows")
    with save_flag(True):
        erp = FakeErpViewer(dialog_on={"fill_line": UNKNOWN_DIALOG})
        world = build_world(erp=erp)
        send_quote(world, s, save=True)
        s.say(f"The viewer raises {UNKNOWN_DIALOG!r} after the first line; no rule knows it.")
        job = run_once(world, s)

    state, final = job_line(world, job)
    s.expect(state == "needs_human", "the robot stopped and asked for a person")
    s.expect(erp.reset_count == 1 and erp.pending_dialog() is None, "the viewer was reset, no dialog left open")
    s.expect(erp.documents == {}, "nothing was saved")
    return s.end(
        "an unknown dialog is never clicked away",
        final,
        state,
        "needs_human",
        "unknown dialog -> Stop -> NEEDS_HUMAN and viewer reset",
    )


def scenario_erp_lies() -> Outcome:
    s = Scenario(4, "The ERP lies about saving")
    states = []
    with save_flag(True):
        for mode, expected_reasons in (
            ("lie_altered", "qty P-100: 2 != 3"),
            ("lie_not_saved", "missing line P-100; missing line P-101"),
        ):
            erp = FakeErpViewer(save_mode=mode)
            world = build_world(erp=erp)
            send_quote(world, s, save=True)
            s.say(f"save_mode={mode!r}: the viewer will say 'Saved.' whatever it stores.")
            job = run_once(world, s)
            state, final = job_line(world, job)
            states.append(state)
            s.say(f"The ERP holds {document_text(erp.documents.get(job))}")
            s.expect(world.queue.status(job).detail == expected_reasons, f"reasons are {expected_reasons!r}")
            s.expect(state == "needs_human", f"{mode}: the job needs a person")
    return s.end(
        "'Saved.' was shown both times, the read back did not agree, so nobody trusts it",
        final,
        "needs_human" if states == ["needs_human", "needs_human"] else ",".join(states),
        "needs_human",
        "a lying save message is caught by read back and compare",
    )


def scenario_forbidden_function() -> Outcome:
    s = Scenario(5, "The bot tries a forbidden function")
    with save_flag(False):
        erp = FakeErpViewer()
        world = build_world(erp=erp, recipe=RecipeThatPrints())
        send_quote(world, s, save=False)
        s.say("A recipe appends Call('print_form') after typing the quote.")
        job = run_once(world, s)
        state, final = job_line(world, job)
        s.expect(state == "needs_human", "the policy denied the call")
        s.expect(erp.dangerous_calls == [], f"viewer.dangerous_calls == {erp.dangerous_calls}: it never reached the ERP")
        s.expect(erp.reset_count == 1, "the viewer was reset")

    with save_flag(True):
        erp2 = FakeErpViewer()
        world2 = build_world(erp=erp2, recipe=RecipeThatSavesAnyway())
        send_quote(world2, s, save=False)
        s.say("Flag on, but the operator did not ask to save, and a recipe adds a save step anyway.")
        job2 = run_once(world2, s)
        _, final2 = job_line(world2, job2)
        s.expect(world2.queue.status(job2).state is JobState.NEEDS_HUMAN, "the save step was denied")
        s.expect(erp2.documents == {}, "nothing was saved")

    s.say("The save lock, asked directly (ActionPolicy.check_call on QuoteScreen / save_form):")
    for allow_save, saving in ((False, False), (False, True), (True, False), (True, True)):
        verdict = world.policy.check_call("QuoteScreen", "save_form", allow_save, saving)
        s.say(f"  allow_save={allow_save!s:5} saving={saving!s:5} -> {verdict}")
    s.expect(
        [type(world.policy.check_call("QuoteScreen", "save_form", a, b)).__name__ for a, b in ((False, True), (True, False), (True, True))]
        == ["Deny", "Deny", "Allow"],
        "only with both locks open is save_form allowed",
    )
    return s.end(
        "print_form is not on the allow-list, and save needs both locks",
        f"{final}; {final2}",
        state,
        "needs_human",
        "not listed means not allowed; one lock alone is a Deny",
    )


def scenario_error_duplicate_stop() -> Outcome:
    s = Scenario(6, "Adapter error, duplicate send, STOP")
    with save_flag(False):
        erp = FakeErpViewer(fail_on=("fill_line",))
        world = build_world(erp=erp)
        send_quote(world, s, save=False)
        s.say("fill_line fails inside the viewer.")
        job = run_once(world, s)
        state, final = job_line(world, job)
        s.expect(state == "failed", "the job failed with the error text")
        s.expect(erp.reset_count == 1, "the viewer was reset, best effort")
        s.expect(run_next_job(world) is None, "no retry: the failed job is not taken again")

        s.say(f"Sending quote {job} a second time:")
        try:
            sent_quote_becomes_job(world, job, request_save=False)
            refused = "no error"
        except QuoteSent as error:
            refused = f"QuoteSent: {error}"
        s.say(refused)
        queued_again = world.queue.enqueue(job, {"job": job, "lines": [], "save": False})
        s.expect(not queued_again and world.queue.list() == [job], "the queue still has one job with that id")

        s.say("Two quotes are queued; an operator hits STOP while the first job is running:")
        stopper = ViewerWithStopButton()
        world2 = build_world(erp=stopper)
        stopper.queue = world2.queue
        first = send_quote(world2, s, save=False)
        second = send_quote(world2, s, save=False)
        run_once(world2, s)
        s.expect(world2.queue.status(first).state is JobState.DONE, "the running job finished")
        s.expect(run_next_job(world2) is None, "take returns nothing while stopped")
        s.expect(world2.queue.status(second).state is JobState.QUEUED, "the waiting job stays queued")
    return s.end(
        "an error ends the job as failed, once; a person re-sends or resumes",
        final,
        state,
        "failed",
        "no sync retries; duplicate ids are refused; STOP lets a running job finish",
    )


SCENARIOS: tuple[Callable[[], Outcome], ...] = (
    scenario_dry_run,
    scenario_save_and_verify,
    scenario_unknown_dialog,
    scenario_erp_lies,
    scenario_forbidden_function,
    scenario_error_duplicate_stop,
)


def print_summary(outcomes: list[Outcome]) -> None:
    rows = [("scenario", "final job state", "what it proves")]
    for outcome in outcomes:
        mark = "" if outcome.ok else " [FAIL]"
        rows.append((f"{outcome.number}. {outcome.title.split(' (')[0]}", outcome.state + mark, outcome.proves))
    widths = [max(len(row[i]) for row in rows) for i in range(3)]
    print()
    print("=== Summary ===")
    for index, row in enumerate(rows):
        print("  " + " | ".join(cell.ljust(width) for cell, width in zip(row, widths)).rstrip())
        if index == 0:
            print("  " + "-+-".join("-" * width for width in widths))
    print()
    print("These are invented fakes; passing says nothing about a real system.")


def main() -> int:
    outcomes = []
    for scenario in SCENARIOS:
        try:
            outcomes.append(scenario())
        except Exception as error:
            number = len(outcomes) + 1
            print(f"  [FAIL] scenario {number} raised {type(error).__name__}: {error}")
            outcomes.append(Outcome(number, scenario.__name__, "error", "-", "-", [str(error)]))
    print_summary(outcomes)
    return 0 if all(outcome.ok for outcome in outcomes) else 1
