# savejournal_v1

Concept `SaveJournal` (`docs/concepts/SaveJournal.md`). Import only from `app.modules.savejournal_v1`; state is in memory inside one `SaveJournal()` instance (reuse the instance across a simulated restart). Inputs and outputs are copies.

- `mark_saving(job, lines: list[dict], known_before: set[str])` (raises `AlreadySaving` if the job has any entry)
- `mark_read_back(job, ref: str)` (raises `UnknownJob` if no entry; allowed from `saving` or `read_back`, updates the ref)
- `phase(job) -> "saving" | "read_back" | None`
- `saved_lines(job) -> list[dict] | None`, `known_before(job) -> frozenset[str] | None`, `saved_ref(job) -> str | None`
- Errors, all `ValueError`s (base `SaveJournalError`): `AlreadySaving`, `UnknownJob`
