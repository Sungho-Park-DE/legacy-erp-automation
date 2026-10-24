import pytest

from app.modules.jobqueue_v1 import (
    InvalidJobId,
    InvalidOutcome,
    JobAlreadyRunning,
    JobQueue,
    JobQueueError,
    JobState,
    JobStatus,
    NotRunning,
    UnknownJob,
)


def test_operational_principle():
    queue = JobQueue()
    assert queue.enqueue("j1", {"n": 1}) is True
    assert queue.enqueue("j2", {"n": 2}) is True

    assert queue.take() == ("j1", {"n": 1})
    queue.finish("j1", JobState.DONE)

    queue.stop()
    assert queue.take() is None
    assert queue.take() is None
    queue.resume()

    assert queue.take() == ("j2", {"n": 2})
    queue.finish("j2", JobState.NEEDS_HUMAN, "screen not allowed")
    assert queue.take() is None
    assert queue.list(JobState.QUEUED) == []

    assert queue.enqueue("j1", {"n": 99}) is False
    assert queue.enqueue("j2", {"n": 99}) is False
    assert queue.list() == ["j1", "j2"]
    assert queue.take() is None


def test_enqueue_twice_keeps_one_job_and_original_payload():
    queue = JobQueue()
    assert queue.enqueue("j", "first") is True
    assert queue.enqueue("j", "second") is False
    assert queue.list() == ["j"]
    assert queue.take() == ("j", "first")
    queue.finish("j", JobState.DONE)
    assert queue.take() is None


def test_enqueue_of_known_id_changes_nothing_in_every_state():
    queue = JobQueue()
    for job in ("d", "h", "f", "r", "q"):
        queue.enqueue(job, job)
    for job, outcome in (("d", JobState.DONE), ("h", JobState.NEEDS_HUMAN), ("f", JobState.FAILED)):
        assert queue.take() == (job, job)
        queue.finish(job, outcome, "why")
    assert queue.take() == ("r", "r")
    before = {j: queue.status(j) for j in ("d", "h", "f", "r", "q")}
    for job in before:
        assert queue.enqueue(job, "other") is False
    assert {j: queue.status(j) for j in before} == before
    assert queue.list() == ["d", "h", "f", "r", "q"]


def test_enqueue_of_done_job_does_not_requeue_it():
    queue = JobQueue()
    queue.enqueue("j", 1)
    queue.take()
    queue.finish("j", JobState.DONE)
    assert queue.enqueue("j", 1) is False
    assert queue.take() is None
    assert queue.status("j").state is JobState.DONE


def test_enqueue_effects_queued_job_without_detail():
    queue = JobQueue()
    queue.enqueue("j", None)
    assert queue.status("j") == JobStatus(JobState.QUEUED, None)


@pytest.mark.parametrize("job", ["", None, 5])
def test_enqueue_requires_non_empty_str_id(job):
    queue = JobQueue()
    with pytest.raises(InvalidJobId):
        queue.enqueue(job, "x")
    assert queue.list() == []


def test_payload_is_opaque_and_returned_as_is():
    payload = object()
    queue = JobQueue()
    queue.enqueue("j", payload)
    job, got = queue.take()
    assert job == "j"
    assert got is payload


def test_take_on_empty_queue_returns_none():
    assert JobQueue().take() is None


def test_take_takes_oldest_queued_and_marks_running():
    queue = JobQueue()
    for job in ("a", "b", "c"):
        queue.enqueue(job, job)
    assert queue.take() == ("a", "a")
    assert queue.status("a").state is JobState.RUNNING
    assert queue.status("b").state is JobState.QUEUED
    assert queue.list(JobState.RUNNING) == ["a"]


def test_take_requires_no_job_running():
    queue = JobQueue()
    queue.enqueue("a", 1)
    queue.enqueue("b", 2)
    queue.take()
    with pytest.raises(JobAlreadyRunning):
        queue.take()
    assert queue.status("b").state is JobState.QUEUED
    queue.finish("a", JobState.DONE)
    assert queue.take() == ("b", 2)


def test_take_while_stopped_returns_none_and_changes_nothing():
    queue = JobQueue()
    queue.enqueue("a", 1)
    queue.stop()
    assert queue.take() is None
    assert queue.status("a").state is JobState.QUEUED
    queue.resume()
    assert queue.take() == ("a", 1)


def test_stop_lets_running_job_finish():
    queue = JobQueue()
    queue.enqueue("a", 1)
    queue.enqueue("b", 2)
    queue.take()
    queue.stop()
    queue.finish("a", JobState.DONE, "ok")
    assert queue.status("a") == JobStatus(JobState.DONE, "ok")
    assert queue.take() is None
    queue.resume()
    assert queue.take() == ("b", 2)


def test_stop_and_resume_are_idempotent():
    queue = JobQueue()
    queue.enqueue("a", 1)
    queue.stop()
    queue.stop()
    queue.resume()
    queue.resume()
    assert queue.take() == ("a", 1)


@pytest.mark.parametrize("outcome", [JobState.DONE, JobState.NEEDS_HUMAN, JobState.FAILED])
def test_finish_sets_state_and_detail_and_never_requeues(outcome):
    queue = JobQueue()
    queue.enqueue("a", 1)
    queue.take()
    queue.finish("a", outcome, "because")
    assert queue.status("a") == JobStatus(outcome, "because")
    assert queue.list(JobState.QUEUED) == []
    assert queue.list(JobState.RUNNING) == []
    assert queue.take() is None


def test_finish_detail_is_optional():
    queue = JobQueue()
    queue.enqueue("a", 1)
    queue.take()
    queue.finish("a", JobState.DONE)
    assert queue.status("a").detail is None


def test_finish_requires_job_running():
    queue = JobQueue()
    queue.enqueue("a", 1)
    queue.enqueue("b", 2)
    with pytest.raises(NotRunning):
        queue.finish("a", JobState.DONE)
    queue.take()
    with pytest.raises(NotRunning):
        queue.finish("b", JobState.DONE)
    queue.finish("a", JobState.DONE)
    with pytest.raises(NotRunning):
        queue.finish("a", JobState.FAILED)
    assert queue.status("a").state is JobState.DONE
    assert queue.status("b").state is JobState.QUEUED


def test_finish_unknown_job():
    with pytest.raises(UnknownJob):
        JobQueue().finish("nope", JobState.DONE)


@pytest.mark.parametrize("outcome", [JobState.QUEUED, JobState.RUNNING, "done", None])
def test_finish_outcome_must_be_terminal(outcome):
    queue = JobQueue()
    queue.enqueue("a", 1)
    queue.take()
    with pytest.raises(InvalidOutcome):
        queue.finish("a", outcome)
    assert queue.status("a").state is JobState.RUNNING


def test_status_unknown_job():
    with pytest.raises(UnknownJob):
        JobQueue().status("nope")


def test_list_is_in_enqueue_order_and_filters_by_state():
    queue = JobQueue()
    for job in ("c", "a", "b", "d"):
        queue.enqueue(job, job)
    assert queue.list() == ["c", "a", "b", "d"]
    queue.take()
    queue.finish("c", JobState.DONE)
    queue.take()
    queue.finish("a", JobState.FAILED)
    queue.take()
    assert queue.list() == ["c", "a", "b", "d"]
    assert queue.list(JobState.DONE) == ["c"]
    assert queue.list(JobState.FAILED) == ["a"]
    assert queue.list(JobState.RUNNING) == ["b"]
    assert queue.list(JobState.QUEUED) == ["d"]
    assert queue.list(JobState.NEEDS_HUMAN) == []


def test_list_returns_a_copy():
    queue = JobQueue()
    queue.enqueue("a", 1)
    queue.list().clear()
    assert queue.list() == ["a"]


def test_states_are_the_five_spec_states():
    assert {s.value for s in JobState} == {"queued", "running", "done", "needs_human", "failed"}


def test_errors_are_value_errors():
    for exc in (UnknownJob, NotRunning, JobAlreadyRunning, InvalidOutcome, InvalidJobId):
        assert issubclass(exc, JobQueueError)
        assert issubclass(exc, ValueError)
