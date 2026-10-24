# Adapters

Everything that talks to an outside system lives here, and nowhere else. Concepts (`app/modules`) never import this folder; only `app/syncs` and entry points do.

| Port (`ports.py`) | Fake | Chosen by |
|---|---|---|
| `ErpViewer` + `ErpRecipe` | `FakeErpViewer`, `FakeRecipe` | `LEA_ERP=fake` |
| `Catalog` | `FakeCatalog` | `LEA_CATALOG=fake` |
| `PhoneLog` | `ScriptedPhone` | `LEA_PHONE=fake` |
| `ScreenText` | `ScriptedScreen` | `LEA_SCREEN=fake` |

The fakes are invented. They show the shape of the problem (dialogs that pop up, a save message that can lie, screen text that flickers), not any real product's behaviour. Passing tests here say nothing about a real system.

## Fake behaviour reference

Chosen by the factories in `app/adapters/__init__.py` (`make_erp`, `make_recipe`, `make_catalog`, `make_phone`, `make_screen`), which read `app/settings.py` at call time and return fresh fakes. Any setting other than `"fake"` raises `ValueError`: a real adapter is a new module here, chosen in that file. The fakes take times as inputs and never read a clock, sleep, use randomness, threads, the network or files.

### `FakeErpViewer(save_mode="ok", fail_on=(), dialog_on=None, numbering="bot", crash_after_save=False, name_in_removal=None, extra_request=None)`

| Part | Behaviour |
|---|---|
| Screens | `HomeScreen`, `QuoteScreen`, `ListScreen`, `EditScreen` (opened with `open_screen`); popup `ItemPicker` (only via `open_picker`). Starts on `HomeScreen`. Unknown screen: `ViewerError` |
| Functions | `QuoteScreen`: `new_form`, `fill_line`, `open_picker`, `save_form`, and the dangerous `print_form`, `delete_form`, `finalize_form`. `ItemPicker`: `pick_item`, `close_picker`. `ListScreen`: `refresh_list`, `open_row`. `EditScreen`: `load_document`, `remove_line`, `set_line_qty`, `add_line`, `update_form`, and the dangerous `delete_form`, `finalize_form` (acting on the loaded document). `HomeScreen`: none. A function of another screen: `ViewerError` |
| `numbering` | `"bot"`: a document is stored under the `header.ref` the bot typed, header `{"ref"}`. `"erp"`: the viewer assigns `D-0001`, `D-0002`, ... (counter per viewer) and stores header `{"ref": assigned, "note": typed ref}` |
| `crash_after_save` | When the confirmation of `save_form` or `update_form` is answered `True`, the document is stored and logged, then `SimulatedCrash` (a `BaseException`, not an `Exception`: the bot process dying) is raised instead of `Saved.` |
| `name_in_removal` | If set, the `remove_line` dialog names this item instead of the one being removed |
| `extra_request` | If set, appended to the request log after every stored `update` (a hidden extra request) |
| `EditScreen` | `set_value` paths: `header.ref` (document to load), `edit.code`, `edit.qty`, `edit.price`. `load_document` loads a working copy of an existing document's lines (unknown ref: `ViewerError`). `remove_line` needs `edit.code` in the working copy and raises `Remove item <code> from this document?`; `True` removes it. `set_line_qty` sets `edit.qty` (whole number) on line `edit.code`, no dialog. `add_line` adds `edit.code`/`edit.qty`/optional `edit.price`, no dialog; a code already present: `ViewerError`. `update_form` on a locked document raises `ViewerError` at call time; otherwise raises `Save changes to this document?`, and `True` stores the working copy (header kept) and raises `Saved.`. Nothing is stored before `update_form` is accepted; opening `EditScreen` or `reset()` drops the working copy. `save_mode` does not apply to `update_form` |
| `list_documents()` | Only on `ListScreen`, else `ViewerError`. Every stored document in insertion order as `Document(header copy, lines=[])` |
| `request_log()` | Copy of the requests sent, oldest first: `list` (open `ListScreen`, `refresh_list`), `save` (`save_form` stored something), `load`, `update` (+ `extra_request`), `delete` / `finalize` / `print` (dialog answered `True`) |
| `edit_by_person(ref, lines)` | Test hook: replaces a stored document's lines, as a person editing in the ERP would |
| `save_mode` | `"ok"` stores the document as typed. `"lie_not_saved"` shows `Saved.` but stores nothing. `"lie_altered"` shows `Saved.` but stores the first line with qty + 1 |
| `fail_on` | Names of functions or screens that raise `ViewerError` when called or opened (nothing is recorded or done) |
| `dialog_on` | `{function_or_screen: text}`: one extra dialog raised after that call or open succeeds, queued behind the built-in ones |
| Dialog pending | `call` and `open_screen` raise `ViewerError("dialog pending")` until every dialog is answered. Dialogs are answered in the order raised |
| `set_value(path, value)` | Only on `QuoteScreen` with a form in progress. Paths: `header.ref`, `line[i].code`, `line[i].qty`, `line[i].price`. Others: `ViewerError` |
| `fill_line` | Commits `line[n].*` (n = number of lines so far) as a line; needs code and a whole-number qty, price optional |
| `read_back(ref)` | Only on `ListScreen`, else `ViewerError`; an unknown ref reads as an empty document (`lines=[]`), as a list screen would show nothing for it. Returns `Document(header=stored header, lines=[{"code", "qty", "price"}])` (a copy). For a locked document `read_back` and `list_documents` add `"status": "locked"` to the header (the key is absent otherwise) |
| `reset()` | Drops the form in progress and all pending dialogs, goes to `HomeScreen`, `reset_count += 1`. Stored documents stay |

Dialog texts: `save_form` raises `Save this form?` (nothing is stored before it is answered; `False` cancels), and after `True` raises `Saved.`. `open_screen("ListScreen")` and `refresh_list` raise `Loading complete.`. `delete_form` raises `Delete this document?`, `print_form` raises `Print this form?`, `finalize_form` raises `Finalize and lock this quote?`; their effect (document removed, ref added to `printed`, ref added to `locked`, after which `save_form` raises `ViewerError`) happens when the dialog is answered `True`. Tests inject others, for example `Server is restarting in 5 minutes.`.

Public attributes: `documents` (ref -> `Document`), `dangerous_calls` (names of `print_form`, `delete_form`, `finalize_form` calls, recorded at call time), `printed`, `locked`, `reset_count`, `current_screen`, `calls_made` (`(screen, fn)` of every accepted call).

### Others

- `FakeRecipe`: payload `{"job", "lines": [{"code", "name", "qty", "price": Decimal | None}], "save"}`. Steps: `Open("QuoteScreen")`, `Call("new_form")`, `Set("header.ref", job)`, then per line `Set` code, qty, price (only when present, plain decimal string) and `Call("fill_line")`; with `save` a final `Call("save_form", is_save=True)`. It never emits dangerous functions or popups. `read_back_steps(job)` is `[Open("ListScreen"), Call("refresh_list")]`; `read_back_ref(job)` is the job id. `edit_steps(ref, ops)` is `Open("EditScreen")`, `Set("header.ref", ref)`, `Call("load_document")`, then per op: `remove` sets `edit.code` and calls `remove_line`; `qty` sets `edit.code`, `edit.qty` and calls `set_line_qty`; `add` sets `edit.code`, `edit.qty`, `edit.price` (only when present, plain decimal string) and calls `add_line`; finally `Call("update_form", is_save=True)`. `item_in_dialog(text)` returns the code in `Remove item <code> from this document?` (whole text), else `None`.
- `FakeCatalog(rows_by_identifier=None)`: small built-in invented set of 8-character identifiers; an unknown identifier gives `[]`.
- `ScriptedPhone(events)`: `poll()` returns the events not yet returned, each once, then `[]`.
- `ScriptedScreen(readings)`: `read()` returns the next `ScreenReading`, then `None`. `flicker(identifier, start, step, partial=None, settle_readings=3, noise=None)` builds a loading sequence: one empty reading, one reading per `partial` text (default: half of the identifier), then `settle_readings` readings of the identifier; with `noise` the settled readings carry a second candidate and no selection.
