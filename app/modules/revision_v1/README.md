# revision_v1

Spec: `docs/concepts/Revision.md`. Pure decisions, no I/O.

- `plan(base, current, target)` -> `Steps(ops)` or `Stop(reason, diffs)`. Lines are `{"code", "qty", "price"?}`; `current` is `None` or `{"header": {"ref", "status"?}, "lines": [...]}`. Quantities compare as numbers (`"2"` equals `2`).
- Stop reasons, checked in this order: `not found`, `locked`, `duplicate code`, `changed since saved` (diffs like `qty B: 1 != 5`, `missing A`, `extra C`), `nothing to change`.
- Ops: removes, then qty changes, then adds (each in base/target order). `add` carries `price` only when the target line has one.
- `may_confirm_removal(named, removing)` -> true only if both given and equal after `strip().upper()`.
- `check_requests(log, update, dangerous)` -> `Ok()` or `Stop("dangerous request <name>")` / `Stop("update sent <n> times")`.
