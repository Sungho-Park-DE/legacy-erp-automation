# jobqueue_v1

Concept `JobQueue` (`docs/concepts/JobQueue.md`). Import only from `app.modules.jobqueue_v1`; state is in memory inside one `JobQueue()` instance, payload is opaque.

- `enqueue(job: str, payload) -> bool` (False and no change if the id is known in any state)
- `take() -> (JobId, payload) | None` (None if stopped or nothing queued; raises `JobAlreadyRunning` if a job is running)
- `finish(job, outcome: JobState, detail=None)` (outcome is `DONE`, `NEEDS_HUMAN` or `FAILED`; the job must be running)
- `stop()` / `resume()` (a running job may still finish)
- `status(job) -> JobStatus(state, detail)`, `list(state: JobState | None = None) -> list[JobId]` in enqueue order
- `JobState`: `QUEUED`, `RUNNING`, `DONE`, `NEEDS_HUMAN`, `FAILED`
- Errors, all `ValueError`s (base `JobQueueError`): `InvalidJobId`, `UnknownJob`, `JobAlreadyRunning`, `NotRunning`, `InvalidOutcome`
