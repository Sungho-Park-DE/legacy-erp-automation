# Adapters

Everything that talks to an outside system lives here, and nowhere else. Concepts (`app/modules`) never import this folder; only `app/syncs` and entry points do.

| Port (`ports.py`) | Fake | Chosen by |
|---|---|---|
| `ErpViewer` + `ErpRecipe` | `FakeErpViewer`, `FakeRecipe` | `LEA_ERP=fake` |
| `Catalog` | `FakeCatalog` | `LEA_CATALOG=fake` |
| `PhoneLog` | `ScriptedPhone` | `LEA_PHONE=fake` |
| `ScreenText` | `ScriptedScreen` | `LEA_SCREEN=fake` |

The fakes are invented. They show the shape of the problem (dialogs that pop up, a save message that can lie, screen text that flickers), not any real product's behaviour. Passing tests here say nothing about a real system.
