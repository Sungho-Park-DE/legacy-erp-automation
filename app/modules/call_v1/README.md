# call_v1

Spec: `docs/concepts/Call.md`. Standard library only; time is always an argument.

- `Calls()` keeps state in memory. `CallId` is an `int`.
- `ring(number: str, at: datetime) -> CallId`.
- `hang_up(call: CallId, at: datetime) -> None`. Raises `UnknownCall` or `CallAlreadyEnded` (both subclass `ValueError`).
- `attach(item: str, at: datetime, before: timedelta, after: timedelta) -> CallId | None`. Window edges are inclusive; the most recent call by `rang_at` (ties: the later `ring`) that matches wins; an open call has no upper limit; no double-adding.
- `recent(limit: int | None = None) -> list[CallView]`, most recent `rang_at` first; `None` means all, a negative limit raises `ValueError`.
- `CallView(call, number, rang_at, ended_at, items: tuple[str, ...])` is a frozen snapshot.
