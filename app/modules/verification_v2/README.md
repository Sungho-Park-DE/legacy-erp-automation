# verification_v2

Spec: `docs/concepts/Verification.md`, section "Version 2" (flag `VERIFICATION_V2`). Pure, no I/O.

- `compare(job, expected, actual)` / `result(job)`: same shapes as v1. Lines are a bag of `(code, qty)`: order is irrelevant and repeated codes are fine if counts match. Reasons: `missing A x2`, `extra B x1`, `price A: 12.5 != 13`, `header ref: 'x' != 'y'`.
- If an actual line has a `ref` different from `actual["header"]["ref"]`, the result is only `Mismatch(("line from another document <ref>",))`.
- A price in `expected` must equal (numerically) the price of some actual line with the same code and qty.
- `locate(job, documents, known_before)`: candidates are documents with `note == job` and `ref` not in `known_before`; returns `Found(ref)`, `NotFound()` or `Many(refs)` (sorted tuple).
