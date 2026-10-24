from decimal import Decimal

import pytest

from app.adapters import FakeErpViewer, SimulatedCrash
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
