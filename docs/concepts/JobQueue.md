# Concept: JobQueue [Payload]

**Purpose:** Hand work to a bot one job at a time, in order, with a switch a person can flip to stop it, and never do the same job twice.

**Operational principle:** If two jobs are queued, then `take` returns the first; if the queue is stopped, `take` returns nothing until it is resumed; a job that finished with NEEDS_HUMAN is not taken again; queueing the same job id twice keeps one job.

**State:**
- jobs: JobId -> { payload: Payload, state: queued | running | done | needs_human | failed, detail: str? }
- order: list JobId
- stopped: bool

**Actions:**
- enqueue(job, payload) -> bool
  - effects: a queued job; returns False and changes nothing if the id is already known (whatever its state)
- take() -> (JobId, Payload)?
  - requires: not stopped and no job running
  - effects: the oldest queued job becomes running
- finish(job, outcome: done | needs_human | failed, detail)
  - requires: job is running
  - effects: state = outcome; no outcome puts the job back in the queue
- stop() / resume()
  - effects: stopped = true / false; a running job is allowed to finish

**Queries:**
- status(job) -> { state, detail }
- list(state?) -> list JobId

**Not this concept's job:** what a job does (syncs + ERP adapter), whether an action is allowed (ActionPolicy), retrying (a person re-sends, which is a new job).
