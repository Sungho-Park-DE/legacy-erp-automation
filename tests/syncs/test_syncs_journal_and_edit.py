from decimal import Decimal

import pytest

from app.adapters import FakeErpViewer, FakeRecipe, SimulatedCrash, ViewerError
from app.modules.jobqueue_v1 import JobState
from app.syncs import build_world, edit_becomes_job, recover_interrupted_jobs, run_next_job

LINES = [{"code": "A-1", "name": "a", "qty": 2, "price": Decimal("12.50")}, {"code": "B-2", "name": "b", "qty": 1, "price": None}]


@pytest.fixture(autouse=True)
def flags(monkeypatch):
    monkeypatch.setenv("LEA_FLAG_SAVE", "1")
    monkeypatch.delenv("LEA_FLAG_VERIFICATION_V2", raising=False)


@pytest.fixture
def v2(monkeypatch):
    monkeypatch.setenv("LEA_FLAG_VERIFICATION_V2", "1")


def enqueue(world, job="J1", lines=LINES, save=True):
    world.queue.enqueue(job, {"job": job, "lines": [dict(line) for line in lines], "save": save})
    return job


def state(world, job):
    return world.queue.status(job)


def saved(erp):
    world = build_world(erp=erp)
    enqueue(world)
    run_next_job(world)
    assert state(world, "J1").state is JobState.DONE, state(world, "J1")
    return world


# --- save journal and restart ---


def test_save_is_journaled_before_the_save_call():
    world = saved(FakeErpViewer())
    assert world.journal.phase("J1") == "read_back"
    assert world.journal.saved_ref("J1") == "J1"
    events = [(e.sync, e.what) for e in world.log]
    assert events.index(("SaveIsJournaled", "journaled before save")) < next(
        i for i, e in enumerate(world.log) if e.what == "called" and e.data.get("fn") == "save_form"
    )


def test_crash_after_save_is_read_back_only_after_restart():
    erp = FakeErpViewer(crash_after_save=True)
    world = build_world(erp=erp)
    enqueue(world)
    with pytest.raises(SimulatedCrash):
        run_next_job(world)
    assert state(world, "J1").state is JobState.RUNNING

    restarted = build_world(erp=erp, queue=world.queue, journal=world.journal)
    assert recover_interrupted_jobs(restarted) == ["J1"]
    assert state(restarted, "J1").state is JobState.DONE
    assert erp.request_log().count("save") == 1
    assert [fn for _screen, fn in erp.calls_made].count("save_form") == 1


def test_interrupted_before_save_needs_a_person():
    erp = FakeErpViewer()
    world = build_world(erp=erp)
    enqueue(world)
    world.queue.take()
    restarted = build_world(erp=erp, queue=world.queue, journal=world.journal)
    recover_interrupted_jobs(restarted)
    assert state(restarted, "J1").state is JobState.NEEDS_HUMAN
    assert state(restarted, "J1").detail == "interrupted before saving"
    assert erp.documents == {}


def test_a_second_save_of_the_same_job_is_refused():
    world = build_world()
    world.journal.mark_saving("J1", LINES, frozenset())
    enqueue(world)
    run_next_job(world)
    assert state(world, "J1").state is JobState.NEEDS_HUMAN
    assert state(world, "J1").detail == "save already attempted"
    assert world.erp.documents == {}


# --- verification v2: the ERP numbers documents ---


def test_v2_locates_the_new_document_among_older_ones(v2):
    erp = FakeErpViewer(numbering="erp")
    world = build_world(erp=erp)
    enqueue(world, "OLD")
    run_next_job(world)
    enqueue(world, "J1")
    run_next_job(world)
    assert state(world, "J1").state is JobState.DONE, state(world, "J1")
    assert world.journal.saved_ref("J1") == "D-0002"
    assert world.journal.known_before("J1") == frozenset({"D-0001"})


def test_v2_document_not_found_needs_a_person(v2):
    world = build_world(erp=FakeErpViewer(numbering="erp", save_mode="lie_not_saved"))
    enqueue(world)
    run_next_job(world)
    assert state(world, "J1").detail == "saved document not found"


def test_v1_with_erp_numbering_cannot_find_the_document():
    world = build_world(erp=FakeErpViewer(numbering="erp"))
    enqueue(world)
    run_next_job(world)
    assert state(world, "J1").state is JobState.NEEDS_HUMAN


# --- changing a saved document ---


def edited(world, lines, job="E1"):
    assert edit_becomes_job(world, "J1", lines, job)
    run_next_job(world)
    return state(world, job)


TARGET = [{"code": "A-1", "qty": 3, "price": Decimal("12.50")}]


def test_edit_removes_and_changes_and_is_verified():
    world = saved(FakeErpViewer())
    result = edited(world, TARGET)
    assert result.state is JobState.DONE, result
    assert [(line["code"], line["qty"]) for line in world.erp.documents["J1"].lines] == [("A-1", 3)]
    assert world.erp.dangerous_calls == []


def test_edit_stops_when_a_person_changed_the_document():
    world = saved(FakeErpViewer())
    world.erp.edit_by_person("J1", [{"code": "A-1", "qty": 2, "price": "12.50"}, {"code": "B-2", "qty": 5, "price": None}])
    log_before = list(world.erp.request_log())
    result = edited(world, TARGET)
    assert result.state is JobState.NEEDS_HUMAN
    assert result.detail.startswith("changed since saved")
    assert "update" not in world.erp.request_log()[len(log_before):]


def test_edit_rejects_a_removal_question_about_another_item():
    world = saved(FakeErpViewer(name_in_removal="Z-9"))
    result = edited(world, TARGET)
    assert result.state is JobState.NEEDS_HUMAN
    assert "names Z-9" in result.detail
    assert [line["code"] for line in world.erp.documents["J1"].lines] == ["A-1", "B-2"]


def test_edit_with_an_unexpected_request_needs_a_person():
    world = saved(FakeErpViewer(extra_request="finalize"))
    result = edited(world, TARGET)
    assert result.state is JobState.NEEDS_HUMAN
    assert result.detail == "dangerous request finalize"


def test_edit_of_a_locked_document_stops():
    world = saved(FakeErpViewer())
    world.erp.locked.add("J1")
    result = edited(world, TARGET)
    assert result.detail == "locked"


def test_edit_needs_a_saved_document():
    world = build_world()
    with pytest.raises(ValueError):
        edit_becomes_job(world, "J1", TARGET, "E1")


def test_edit_needs_a_job_that_ended_as_done():
    erp = FakeErpViewer(save_mode="lie_altered")
    world = build_world(erp=erp)
    enqueue(world)
    run_next_job(world)
    assert state(world, "J1").state is JobState.NEEDS_HUMAN
    with pytest.raises(ValueError, match="did not end as done"):
        edit_becomes_job(world, "J1", TARGET, "E1")


def test_edit_with_the_save_flag_off_is_a_dry_run(monkeypatch):
    erp = FakeErpViewer()
    world = saved(erp)
    monkeypatch.delenv("LEA_FLAG_SAVE")
    updates = erp.request_log().count("update")
    result = edited(world, TARGET)
    assert (result.state, result.detail) == (JobState.DONE, "dry run")
    assert erp.request_log().count("update") == updates
    assert [(line["code"], line["qty"]) for line in erp.documents["J1"].lines] == [("A-1", 2), ("B-2", 1)]


def test_the_edit_job_carries_the_save_flag_as_it_was_when_it_was_queued(monkeypatch):
    world = saved(FakeErpViewer())
    assert edit_becomes_job(world, "J1", TARGET, "E-on")
    assert world.queue.payload("E-on")["save"] is True
    monkeypatch.delenv("LEA_FLAG_SAVE")
    assert edit_becomes_job(world, "J1", TARGET, "E-off")
    assert world.queue.payload("E-off")["save"] is False


def test_a_second_edit_must_name_the_latest_job_that_changed_the_document():
    world = saved(FakeErpViewer())
    assert edited(world, TARGET, "E1").state is JobState.DONE
    again = [{"code": "A-1", "qty": 4, "price": Decimal("12.50")}]
    assert edit_becomes_job(world, "J1", again, "E2")
    run_next_job(world)
    assert state(world, "E2").detail.startswith("changed since saved")
    assert edit_becomes_job(world, "E1", again, "E3")
    run_next_job(world)
    assert state(world, "E3").state is JobState.DONE


# --- errors after the save was started, refused questions, prices ---


class ErrorAfterSave(FakeErpViewer):
    def _finish_save(self):
        raise ViewerError("timeout after the save")


def test_error_after_the_save_went_through_needs_a_person_not_failed():
    erp = ErrorAfterSave()
    world = build_world(erp=erp)
    enqueue(world)
    run_next_job(world)
    result = state(world, "J1")
    assert result.state is JobState.NEEDS_HUMAN
    assert result.detail.startswith("error after the save was started")
    assert "J1" in erp.documents


def test_error_before_any_save_is_still_failed():
    world = build_world(erp=FakeErpViewer(fail_on=("fill_line",)))
    enqueue(world)
    run_next_job(world)
    assert state(world, "J1").state is JobState.FAILED


def test_a_removal_question_the_rules_refuse_stops_the_change_before_the_update():
    erp = FakeErpViewer(name_in_removal="DELETE-1")
    world = saved(erp)
    updates = erp.request_log().count("update")
    result = edited(world, TARGET)
    assert result.state is JobState.NEEDS_HUMAN
    assert result.detail.startswith("removal question refused by the rules")
    assert erp.request_log().count("update") == updates
    assert [(line["code"], line["qty"]) for line in erp.documents["J1"].lines] == [("A-1", 2), ("B-2", 1)]


def test_a_changed_price_stops_the_change_before_anything_is_typed():
    erp = FakeErpViewer()
    world = saved(erp)
    updates = erp.request_log().count("update")
    result = edited(world, [{"code": "A-1", "qty": 3, "price": Decimal("99.00")}])
    assert (result.state, result.detail.split(":")[0]) == (JobState.NEEDS_HUMAN, "price change not supported")
    assert erp.request_log().count("update") == updates


def test_a_price_a_person_changed_is_seen_before_the_change():
    erp = FakeErpViewer()
    world = saved(erp)
    erp.edit_by_person("J1", [{"code": "A-1", "qty": 2, "price": "50"}, {"code": "B-2", "qty": 1, "price": None}])
    updates = erp.request_log().count("update")
    result = edited(world, TARGET)
    assert result.state is JobState.NEEDS_HUMAN
    assert result.detail.startswith("changed since saved: price A-1")
    assert erp.request_log().count("update") == updates


def test_v2_with_the_bot_numbering_does_not_find_the_document(v2):
    erp = FakeErpViewer(numbering="bot")
    world = build_world(erp=erp)
    enqueue(world)
    run_next_job(world)
    assert (state(world, "J1").state, state(world, "J1").detail) == (JobState.NEEDS_HUMAN, "saved document not found")
    assert "J1" in erp.documents


class RecipeThatMisnamesItsRemovalFunction:
    """Types exactly like FakeRecipe but reports another name for the removal function."""

    removal_fn = "not_the_removal_function"

    def __init__(self):
        self._inner = FakeRecipe()

    def __getattr__(self, name):
        return getattr(self._inner, name)


def test_the_item_check_does_not_depend_on_the_recipe_naming_the_removal_function():
    erp = FakeErpViewer(name_in_removal="Z-9")
    world = saved(erp)
    world.recipe = RecipeThatMisnamesItsRemovalFunction()
    result = edited(world, TARGET)
    assert result.state is JobState.NEEDS_HUMAN
    assert "names Z-9" in result.detail
