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
