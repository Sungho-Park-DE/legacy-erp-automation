# sighting_v1

Spec: `docs/concepts/Sighting.md`. Standard library only; time is always an argument.

- `Sighting()` keeps state in memory.
- `observe(candidates: list[str], selected: str | None, at: datetime, needed: int, quiet: timedelta) -> Result`. Raises `ValueError` if `needed < 1`. Duplicate candidates in one reading count as one.
- `Result` is one of the frozen dataclasses `Confirmed(id)`, `Pending()`, `Ambiguous()`, `Repeated()`; match with `isinstance`.
- `last_confirmed(id: str) -> datetime | None`.
- Quiet rule: a confirmation exactly `quiet` ago is NOT repeated (`Repeated` only if `at - last < quiet`). `Repeated` does not move `last_confirmed`.
