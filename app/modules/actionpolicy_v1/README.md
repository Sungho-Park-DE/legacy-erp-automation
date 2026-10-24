# actionpolicy_v1

Spec: `docs/concepts/ActionPolicy.md`. Rules come from `app/data/policy.json`; the module does no file I/O.

- `ActionPolicy().load(rules: dict)` raises `ValueError` if a save call is not in `calls` or a function name contains a forbidden word; keys starting with `_` and unknown keys are ignored.
- `check_screen(screen, parent=None, opener=None)` and `check_call(screen, fn, allow_save, saving)` return `Allow()` or `Deny(reason)`.
- `classify_dialog(text, saving, during=None)` returns `Accept()`, `Reject()` or `Stop(reason)`; patterns must match the whole text.
- `rules()` returns a copy of the loaded rules for showing to a person.
- Results are frozen dataclasses exported from `__init__`. Anything not listed is denied.
