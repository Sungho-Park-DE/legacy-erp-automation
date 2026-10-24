from decimal import Decimal

import pytest

from app.adapters import FakeErpViewer, FakeRecipe
from app.adapters.ports import Call, Document, Open, Set
from app.modules.jobqueue_v1 import JobState
from app.modules.verification_v1 import Match, Mismatch
from app.syncs import (
    adapter_error_finishes_job,
    build_world,
    operator_adds_catalog_line,
    operator_sets_price,
    run_next_job,
    saved_job_is_read_back,
    sent_quote_becomes_job,
    verification_finishes_job,
)

IDENTIFIER = "K7Q2M9X4"


class ScriptRecipe:
    def __init__(self, extra=(), read_back=None, replace=None):
        self.inner = FakeRecipe()
        self.extra = list(extra)
        self.read_back = read_back
        self.replace = replace

    def steps(self, payload):
        base = self.replace if self.replace is not None else self.inner.steps(payload)
        return list(base) + self.extra

    def read_back_steps(self, job):
        return self.read_back if self.read_back is not None else self.inner.read_back_steps(job)

    def read_back_ref(self, job):
        return self.inner.read_back_ref(job)


class ResetFails(FakeErpViewer):
    def reset(self):
        raise RuntimeError("viewer is gone")


@pytest.fixture(autouse=True)
def save_flag_off(monkeypatch):
    monkeypatch.delenv("LEA_FLAG_SAVE", raising=False)


@pytest.fixture
def save_flag_on(monkeypatch):
    monkeypatch.setenv("LEA_FLAG_SAVE", "1")


def queue_quote(world, save, price=True):
    quote = world.quotes.open()
    first, _ = operator_adds_catalog_line(world, quote, IDENTIFIER, qty=2)
    if price:
        operator_sets_price(world, quote, first, Decimal("12.50"))
    sent_quote_becomes_job(world, quote, request_save=save)
    return quote


def status(world, job):
    state = world.queue.status(job)
    return state.state, state.detail


def test_nothing_queued_or_stopped_means_no_job():
    world = build_world()
    assert run_next_job(world) is None
    job = queue_quote(world, save=False)
    world.queue.stop()
    assert run_next_job(world) is None
    assert world.queue.status(job).state is JobState.QUEUED


def test_dry_run_types_everything_then_resets_without_saving():
    world = build_world()
    job = queue_quote(world, save=True)
    assert run_next_job(world) == job
    assert status(world, job) == (JobState.DONE, "dry run")
    assert world.erp.documents == {}
    assert world.erp.reset_count == 1
    assert ("QuoteScreen", "save_form") not in world.erp.calls_made
    assert [fn for _, fn in world.erp.calls_made] == ["new_form", "fill_line", "fill_line"]


def test_saved_job_is_read_back_and_verified(save_flag_on):
    world = build_world()
    job = queue_quote(world, save=True)
    run_next_job(world)
    assert status(world, job) == (JobState.DONE, "saved and verified")
    document = world.erp.documents[job]
    assert [(line["code"], line["qty"], line["price"]) for line in document.lines] == [
        ("P-100", 2, "12.50"),
        ("P-101", 2, None),
    ]
    assert world.verification.result(job) == Match()
    assert ("QuoteScreen", "save_form") in world.erp.calls_made
    assert ("ListScreen", "refresh_list") in world.erp.calls_made
    texts = [e.data["text"] for e in world.log if e.what == "dialog accepted"]
    assert texts == ["Save this form?", "Saved.", "Loading complete.", "Loading complete."]


def test_flag_on_but_quote_not_sent_for_saving_is_still_a_dry_run(save_flag_on):
    world = build_world()
    job = queue_quote(world, save=False)
    run_next_job(world)
    assert status(world, job) == (JobState.DONE, "dry run")
    assert world.erp.documents == {}


def test_flag_switched_off_after_send_is_denied_at_the_save_step(save_flag_on, monkeypatch):
    world = build_world()
    job = queue_quote(world, save=True)
    monkeypatch.delenv("LEA_FLAG_SAVE")
    run_next_job(world)
    state, detail = status(world, job)
    assert state is JobState.NEEDS_HUMAN
    assert "saving is not permitted" in detail
    assert world.erp.documents == {}
    assert world.erp.reset_count == 1


def test_save_step_in_a_dry_run_is_denied_by_the_policy():
    world = build_world(recipe=ScriptRecipe(extra=[Call("save_form", is_save=True)]))
    job = queue_quote(world, save=True)
    run_next_job(world)
    state, detail = status(world, job)
    assert state is JobState.NEEDS_HUMAN
    assert detail == "saving is not permitted for this job: 'save_form'"
    assert world.erp.documents == {}
    assert ("QuoteScreen", "save_form") not in world.erp.calls_made


def test_save_function_outside_the_save_step_is_denied_even_with_both_flags(save_flag_on):
    steps = [Open("QuoteScreen"), Call("new_form"), Set("header.ref", "Q1"), Call("save_form", is_save=False)]
    world = build_world(recipe=ScriptRecipe(replace=steps))
    job = queue_quote(world, save=True)
    run_next_job(world)
    state, detail = status(world, job)
    assert state is JobState.NEEDS_HUMAN
    assert "only allowed in the save step" in detail
    assert world.erp.documents == {}


def test_unknown_dialog_stops_the_bot():
    world = build_world(erp=FakeErpViewer(dialog_on={"fill_line": "Server is restarting in 5 minutes."}))
    job = queue_quote(world, save=False)
    run_next_job(world)
    state, detail = status(world, job)
    assert state is JobState.NEEDS_HUMAN
    assert "Server is restarting in 5 minutes." in detail
    assert world.erp.reset_count == 1
    assert world.erp.pending_dialog() is None
    assert [fn for _, fn in world.erp.calls_made] == ["new_form", "fill_line"]


def test_dialog_that_the_policy_rejects_is_answered_no_and_the_job_goes_on():
    erp = FakeErpViewer(dialog_on={"new_form": "Delete this document?"})
    world = build_world(erp=erp)
    job = queue_quote(world, save=False)
    run_next_job(world)
    assert status(world, job) == (JobState.DONE, "dry run")
    assert [e.what for e in world.log if e.what.startswith("dialog")] == ["dialog rejected"]
    assert erp.dangerous_calls == []


def test_forbidden_function_is_denied_and_never_reaches_the_erp():
    world = build_world(recipe=ScriptRecipe(extra=[Call("print_form")]))
    job = queue_quote(world, save=False)
    run_next_job(world)
    state, detail = status(world, job)
    assert state is JobState.NEEDS_HUMAN
    assert detail == "function 'print_form' is not allowed on 'QuoteScreen'"
    assert world.erp.dangerous_calls == []
    assert world.erp.printed == []
    assert world.erp.reset_count == 1


def test_screen_outside_the_allow_list_is_denied():
    world = build_world(recipe=ScriptRecipe(replace=[Open("QuoteScreen"), Open("AdminScreen")]))
    job = queue_quote(world, save=False)
    run_next_job(world)
    assert status(world, job) == (JobState.NEEDS_HUMAN, "screen 'AdminScreen' is not allowed")
    assert world.erp.reset_count == 1


def test_popup_is_followed_through_its_opener_and_closed():
    steps = [
        Open("QuoteScreen"),
        Call("new_form"),
        Call("open_picker"),
        Call("pick_item"),
        Call("close_picker"),
        Set("line[0].qty", "1"),
        Call("fill_line"),
    ]
    world = build_world(recipe=ScriptRecipe(replace=steps))
    job = queue_quote(world, save=False)
    run_next_job(world)
    assert status(world, job) == (JobState.DONE, "dry run")
    assert ("ItemPicker", "pick_item") in world.erp.calls_made


def test_popup_cannot_be_opened_as_a_screen_without_its_opener():
    world = build_world(recipe=ScriptRecipe(replace=[Open("QuoteScreen"), Call("new_form"), Open("ItemPicker")]))
    job = queue_quote(world, save=False)
    run_next_job(world)
    state, detail = status(world, job)
    assert state is JobState.NEEDS_HUMAN
    assert "popup 'ItemPicker' may only be opened from 'QuoteScreen' by 'open_picker'" == detail


def test_read_back_goes_through_the_same_checks(save_flag_on):
    recipe = ScriptRecipe(read_back=[Open("ListScreen"), Call("delete_form")])
    world = build_world(recipe=recipe)
    job = queue_quote(world, save=True)
    run_next_job(world)
    state, detail = status(world, job)
    assert state is JobState.NEEDS_HUMAN
    assert "delete_form" in detail
    assert world.erp.dangerous_calls == []
    assert world.erp.reset_count == 1


@pytest.mark.parametrize(
    "mode, reasons",
    [
        ("lie_altered", "qty P-100: 2 != 3"),
        ("lie_not_saved", "missing line P-100; missing line P-101"),
    ],
)
def test_erp_that_lies_about_saving_ends_as_needs_human(save_flag_on, mode, reasons):
    world = build_world(erp=FakeErpViewer(save_mode=mode))
    job = queue_quote(world, save=True)
    run_next_job(world)
    assert status(world, job) == (JobState.NEEDS_HUMAN, reasons)
    assert isinstance(world.verification.result(job), Mismatch)
    assert run_next_job(world) is None


def test_price_is_compared_only_where_the_job_has_one(save_flag_on):
    world = build_world()
    job = queue_quote(world, save=True, price=False)
    run_next_job(world)
    assert status(world, job)[0] is JobState.DONE
    assert world.erp.documents[job].lines[0]["price"] is None


def test_adapter_error_fails_the_job_resets_and_is_not_retried():
    erp = FakeErpViewer(fail_on=("fill_line",))
    world = build_world(erp=erp)
    job = queue_quote(world, save=False)
    run_next_job(world)
    assert status(world, job) == (JobState.FAILED, "ViewerError: fill_line failed")
    assert erp.reset_count == 1
    assert run_next_job(world) is None
    assert erp.reset_count == 1


def test_adapter_error_while_reading_back_also_fails_the_job(save_flag_on):
    world = build_world(erp=FakeErpViewer(fail_on=("refresh_list",)))
    job = queue_quote(world, save=True)
    run_next_job(world)
    assert status(world, job) == (JobState.FAILED, "ViewerError: refresh_list failed")
    assert world.erp.reset_count == 1


def test_adapter_error_finishes_job_even_when_reset_fails():
    world = build_world(erp=ResetFails(fail_on=("new_form",)))
    job = queue_quote(world, save=False)
    run_next_job(world)
    assert status(world, job) == (JobState.FAILED, "ViewerError: new_form failed")


def test_adapter_error_finishes_job_directly():
    world = build_world()
    job = queue_quote(world, save=False)
    world.queue.take()
    adapter_error_finishes_job(world, job, RuntimeError("boom"))
    assert status(world, job) == (JobState.FAILED, "RuntimeError: boom")
    assert world.erp.reset_count == 1


def test_verification_finishes_job_match_and_mismatch():
    world = build_world()
    first = queue_quote(world, save=False)
    second = queue_quote(world, save=False)
    world.queue.take()
    verification_finishes_job(world, first, Match())
    world.queue.take()
    verification_finishes_job(world, second, Mismatch(("qty A: 1 != 3", "missing line B")))
    assert status(world, first) == (JobState.DONE, "saved and verified")
    assert status(world, second) == (JobState.NEEDS_HUMAN, "qty A: 1 != 3; missing line B")


def test_saved_job_is_read_back_compares_the_payload_with_the_erp_document(save_flag_on):
    world = build_world()
    job = queue_quote(world, save=True)
    _, payload = world.queue.take()
    world.erp.documents[job] = Document(
        header={"ref": job},
        lines=[{"code": "P-100", "qty": 2, "price": "12.50"}, {"code": "P-101", "qty": 5, "price": None}],
    )
    saved_job_is_read_back(world, job, payload)
    assert status(world, job) == (JobState.NEEDS_HUMAN, "qty P-101: 2 != 5")


def test_jobs_run_one_after_the_other_and_a_stop_lets_the_running_job_finish():
    class StopsOnFirstCall(FakeErpViewer):
        queue = None

        def call(self, fn):
            self.queue.stop()
            super().call(fn)

    erp = StopsOnFirstCall()
    world = build_world(erp=erp)
    erp.queue = world.queue
    first = queue_quote(world, save=False)
    second = queue_quote(world, save=False)
    assert run_next_job(world) == first
    assert status(world, first)[0] is JobState.DONE
    assert run_next_job(world) is None
    assert world.queue.status(second).state is JobState.QUEUED
    world.queue.resume()
    assert run_next_job(world) == second
    assert status(world, second)[0] is JobState.DONE
