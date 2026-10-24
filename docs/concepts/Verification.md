# Concept: Verification

**Purpose:** Decide whether what the target system now holds is what was meant to be written, without trusting the system's own "saved" message.

**Operational principle:** If the job meant two lines (A x2, B x1) and reading the document back shows A x2 and B x1, the result is a match; if it shows A x2 and B x3, the result is a mismatch with reason `qty B: 1 != 3`; a missing or extra line is a mismatch too.

**State:**
- results: JobId -> Match | Mismatch(reasons: list str)

**Actions:**
- compare(job, expected: { header: dict, lines: list { code, qty, price? } }, actual: same shape) -> Match | Mismatch(reasons)
  - effects: results[job]; lines are matched by code; header keys present in `expected` must be equal in `actual`; a price is compared only where `expected` has one

**Queries:**
- result(job) -> Match | Mismatch?

**Not this concept's job:** reading the document back and turning the target's format into this shape (ERP adapter), what happens on a mismatch (sync -> JobQueue NEEDS_HUMAN).

## Version 2 (`verification_v2`, flag `VERIFICATION_V2`, off by default)

**Purpose (unchanged), plus:** find the document the save created when the target system numbers documents itself, without mistaking an older document for it.

**Operational principle:** If documents D1 existed before the save and after it the list shows D1 and D2, both noted with job J, then `locate` returns D2; if it shows none or two new ones, it says so and a person decides. Lines are compared as a bag of (code, qty): the same lines in another order match, and two lines with the same code are compared as two lines, not refused.

**Actions (in addition to `compare` and `result`, same shapes as version 1):**
- locate(job, documents: list { ref, note? }, known_before: set str) -> Found(ref) | NotFound | Many(refs)
  - candidates are documents whose note equals job and whose ref is not in known_before
  - so the target system must keep the typed reference as the document's note; a system that stores the document under the typed reference itself has no note and always gives NotFound
- compare(job, expected, actual)
  - header keys in `expected` must be equal in `actual`
  - a line in `actual` that carries a `ref` other than `actual.header.ref` -> Mismatch(`line from another document <ref>`) and nothing else is compared
  - lines are matched as a bag of (code, qty); reasons `missing <code> x<qty>` and `extra <code> x<qty>`; a price in `expected` is compared against a line with the same code and qty
