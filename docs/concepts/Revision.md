# Concept: Revision

**Purpose:** Change a document the bot saved earlier without overwriting what a person changed since, and allow a dangerous step (removing a line) only for the exact line being removed.

**Operational principle:** If the bot saved A x2, B x1 and now should make it A x3, then planning against the document as it is now gives one step `qty A 3`; if a person meanwhile changed B to 5, planning stops with `changed since saved`; while removing B, a confirmation that names B may be accepted and one that names any other item may not; after the change the viewer's own request log must show exactly one update and no dangerous request.

**State:** none (pure decisions).

**Actions:**
- plan(base: list Line, current: Document?, target: list Line) -> Steps(ops) | Stop(reason, diffs)
  - Line = { code, qty, price? }; Document = { header: { ref, status? }, lines: list Line }
  - current is none or has no lines -> Stop(`not found`)
  - current.header.status = locked -> Stop(`locked`)
  - current lines differ from base (code and qty, any order) -> Stop(`changed since saved`, diffs)
  - otherwise ops, in this order: `{op: remove, code}` for codes in base not in target, `{op: qty, code, qty}` for codes in both with another qty, `{op: add, code, qty, price?}` for codes only in target; no ops -> Stop(`nothing to change`)
  - a code appearing twice in base, current or target -> Stop(`duplicate code`)
- may_confirm_removal(named: str?, removing: str?) -> bool
  - true only when both are given and equal after trimming and upper-casing
- check_requests(log: list str, update: str, dangerous: set str) -> Ok | Stop(reason)
  - log is the part of the viewer's request log written during the change
  - Stop(`dangerous request <name>`) if any entry is in dangerous; Stop(`update sent <n> times`) if `update` does not appear exactly once

**Not this concept's job:** where base comes from (SaveJournal), reading the current document and typing the ops (ERP adapter and recipe), which dialog texts name an item (recipe), which requests are dangerous (settings).
