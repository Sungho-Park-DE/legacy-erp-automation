# verification_v1

Spec: `docs/concepts/Verification.md`. Pure comparison, no I/O.

- `Verification().compare(job, expected, actual)` where both are `{"header": dict, "lines": [{"code", "qty", "price"?}]}` (plain dicts); returns `Match()` or `Mismatch(reasons: tuple[str, ...])` and remembers it per job.
- `result(job)` returns the last outcome for that job, or `None`.
- Quantities and prices are compared as numbers (`"12.50"` equals `Decimal("12.5")`); a price is checked only when `expected` has one; header keys are taken from `expected` only.
- Reasons: `qty B: 1 != 3`, `price A: 12.5 != 13`, `missing line C`, `extra line D`, `duplicate line A`, `header ref: 'x' != 'y'`.
