from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Generic, TypeVar

Payload = TypeVar("Payload")
JobId = str


class JobState(Enum):
    QUEUED = "queued"
    RUNNING = "running"
    DONE = "done"
    NEEDS_HUMAN = "needs_human"
    FAILED = "failed"


_OUTCOMES = (JobState.DONE, JobState.NEEDS_HUMAN, JobState.FAILED)


class JobQueueError(ValueError):
    pass


class InvalidJobId(JobQueueError):
    pass


class UnknownJob(JobQueueError):
    pass


class JobAlreadyRunning(JobQueueError):
    pass


class NotRunning(JobQueueError):
    pass


class InvalidOutcome(JobQueueError):
    pass


@dataclass(frozen=True)
class JobStatus:
    state: JobState
    detail: str | None = None


class _Job(Generic[Payload]):
    def __init__(self, payload: Payload) -> None:
        self.payload = payload
        self.state = JobState.QUEUED
        self.detail: str | None = None


class JobQueue(Generic[Payload]):
    """take() returns None when stopped or empty, but raises JobAlreadyRunning if a job is running."""

    def __init__(self) -> None:
        self._jobs: dict[JobId, _Job[Payload]] = {}
        self._stopped = False

    def enqueue(self, job: JobId, payload: Payload) -> bool:
        if not isinstance(job, str) or not job:
            raise InvalidJobId(f"job id must be a non-empty str, got {job!r}")
        if job in self._jobs:
            return False
        self._jobs[job] = _Job(payload)
        return True

    def take(self) -> tuple[JobId, Payload] | None:
        if any(j.state is JobState.RUNNING for j in self._jobs.values()):
            raise JobAlreadyRunning("a job is already running")
        if self._stopped:
            return None
        for job_id, job in self._jobs.items():
            if job.state is JobState.QUEUED:
                job.state = JobState.RUNNING
                return job_id, job.payload
        return None

    def finish(self, job: JobId, outcome: JobState, detail: str | None = None) -> None:
        if outcome not in _OUTCOMES:
            raise InvalidOutcome(f"outcome must be done, needs_human or failed, got {outcome!r}")
        entry = self._get(job)
        if entry.state is not JobState.RUNNING:
            raise NotRunning(f"job {job!r} is {entry.state.value}, not running")
        entry.state = outcome
        entry.detail = detail

    def stop(self) -> None:
        self._stopped = True

    def resume(self) -> None:
        self._stopped = False

    def status(self, job: JobId) -> JobStatus:
        entry = self._get(job)
        return JobStatus(entry.state, entry.detail)

    def payload(self, job: JobId) -> Payload:
        return self._get(job).payload

    def list(self, state: JobState | None = None) -> list[JobId]:
        return [j for j, e in self._jobs.items() if state is None or e.state is state]

    def _get(self, job: JobId) -> _Job[Payload]:
        try:
            return self._jobs[job]
        except (KeyError, TypeError):
            raise UnknownJob(f"unknown job {job!r}") from None
