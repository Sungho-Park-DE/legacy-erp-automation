# Volatile decisions

What is known to change before any code exists, and the one place each is hidden.

| Decision | Evidence it will change | Hidden in |
|---|---|---|
| The target ERP's scripting interface (open screen, set value, call form function, dialogs, read instance XML) | Outside system; this repository ships only a fake | `app/adapters`: port `ErpViewer`, fake `FakeErpViewer`, chosen by `LEA_ERP` |
| How a quote is typed into the ERP (which screens, field paths, functions, which call saves) | Depends entirely on the target ERP's screens | `app/adapters/recipe.py` (`ErpRecipe`), next to the adapter |
| The ERP's document format when read back (XML) and its mapping to `{ header, lines }` | Outside format | the ERP adapter (`read_back`) |
| Catalog system (look up rows for an identifier) | Outside system | port `Catalog`, fake `FakeCatalog`, `LEA_CATALOG` |
| Phone system log (rings, hang-ups) | Outside program and file format | port `PhoneLog`, fake `ScriptedPhone`, `LEA_PHONE` |
| Screen text source and how candidates are found in it (window title, label, fixed-length token) | Outside UI; real one is UI Automation on the office PC | port `ScreenText`, fake `ScriptedScreen`, `LEA_SCREEN` |
| Allowed screens, functions, forbidden words, dialog rules | Set by the business owner; changed only by a person | `ActionPolicy`, rules file `app/data/policy.json` |
| Only a person sets prices | Owner's rule | `Quote.set_price` + sync `OperatorSetsPrice` |
| Saving at all (versus dry run only) | Turned on per site by a person | flag `LEA_FLAG_SAVE`, read only in `app/syncs` |
| Sighting: readings needed (2), quiet period (60 s) | Policy values | `app/settings.py` |
| Call window: 10 s before ring, 10 min after hang-up | Policy values | `app/settings.py` |
| Automatic re-login: at most once | Policy value (account lock-out) | `app/settings.py` |
| Supervisor: stop restarting after 3 in a row or 4 per hour | Policy values | `app/settings.py` |
