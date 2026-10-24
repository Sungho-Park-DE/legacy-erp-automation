# Driving a legacy ActiveX form viewer

**Problem:** the ERP's screens are forms drawn by an ActiveX viewer control inside a web page that only works in the browser's Internet Explorer mode. There is no API, and the ERP belongs to someone else, so it cannot be changed.

**Answer:** the viewer already carries a scripting interface for its own forms. The bot uses that interface from outside, over COM, the same way the form's own scripts use it from inside.

This page describes the real adapter (described, not implemented here) and maps it to the `ErpViewer` port in [ports.py](../app/adapters/ports.py), which this repository implements only as a fake. No product, screen, form or function names of the real system appear here.

## Finding the way in

The control ships as a DLL with a type library. The type library lists what can be called from outside: the viewer's window and document, the form's data model (get a value, set a value, refresh), the form's data as XML, grid cells and rows, and the form's script functions. That list, not the network traffic, is what the bot is built on.

## Attaching, step by step

The bot runs on the server as 64-bit Python and uses COM (in the real system through the `comtypes` library).

1. Find the browser's IE rendering window and get its HTML document through COM (the standard `WM_HTML_GETOBJECT` window message).
2. In that page, the viewer is an `<OBJECT>` element. Its `.object` property is the viewer itself.
3. From the viewer's window:
   - `document` gives the form's controls and data model: set a value, then refresh.
   - `javascript` gives the form's own script functions, which can be called by name.
4. The form keeps its whole state in an XML instance. Reading that instance gives the document as data, so nothing has to be read off the screen.

The first real tests followed this order, each one on its own: read only (attach, find the function names without calling them, read the XML), then a dry run that typed one line and reset the form, then the same with the browser minimized, then one real save.

## Why form functions, and not key presses or direct requests

| Way | Why not, or why |
|---|---|
| Key presses and screen coordinates (the first version) | The window has to be in front, the screen resolution fixed and the coordinates measured. It was deleted once the scripting route worked. |
| Calling the site's server addresses directly | Not used. Everything goes through the form, as a person's input does. |
| The form's own functions (chosen) | Calling them makes the form do what it does for a person: in the real tests the viewer's log showed the same requests as for a person's typing, and the form filled in the same fields. It works while the browser is behind other windows or minimized. |

## Pitfalls

| Pitfall | What happens | How the bot deals with it |
|---|---|---|
| Dialogs are modal | A function that raises an alert does not return until the alert is closed, so the bot's own call hangs. | A separate watcher thread looks for dialog windows (the standard Windows dialog class `#32770`), reads the text, asks [ActionPolicy](concepts/ActionPolicy.md), and presses the chosen button with a window message (`BM_CLICK`), without needing focus. A dialog no rule knows stops the job. |
| Popup forms are modal too | Opening a popup by calling its function blocks the same way. | The call is deferred with the page's own `setTimeout`, so it returns at once; the popup is then reached through the viewer's child windows. COM calls keep working while the popup is open. The watcher closes only dialogs, not the popup the bot itself opened. |
| A script result from an earlier run | A script injected into an old IE page cannot return a value directly in every case, so it writes its result into the page, and the bot polls for it. An earlier run's result, or a run that executed but whose answer was lost, can look like the answer to this one. | Every run gets a fresh random token, the result is written together with that token, and only a result carrying this run's token is accepted. A run that executed but whose result was lost is not run again; the bot stops instead. Described, not implemented here. |
| A minimized browser | Minimizing the browser moves the IE rendering window under a hidden top-level window. | The window search includes hidden windows. |
| The login expires | When the tab is in the background or the browser is minimized, the browser does not show the "please log in" alert. The page stays half loaded and nothing says why. | A form that does not finish loading in time is treated as a dropped login: the bot stops, or uses its one automatic re-login (`RELOGIN_MAX = 1`, [bot-safety.md](bot-safety.md), safeguard 6). |

## Mapping to this repository

| `ErpViewer` method | Real adapter | Fake here |
|---|---|---|
| `open_screen(screen)` | Open the screen's page through the ERP's menu and wait until the viewer and its form have loaded | Switches between invented screens |
| `set_value(path, value)` | Set a value in the form's data model or a grid cell, then refresh | Stores the value on the form in progress |
| `call(fn)` | Call a form script function by name through the viewer's script object | Runs an invented function |
| `pending_dialog()`, `answer_dialog(accept)` | The watcher thread's view of open dialog windows, and the button it presses | A queue of dialog texts |
| `read_back(ref)` | Read the XML instance (or the list screen's grid) and turn it into a `Document` | Returns what the fake stored |
| `reset()` | The form's own reset function | Clears the form in progress |

Every call still goes through the same checks as in the demo: the screen and function allow-lists, the save lock, dialog rules and read-back ([bot-safety.md](bot-safety.md)). The real adapter only replaces the fake behind the port.

## What is not here

The real adapter code, the ERP's form definitions, function names and dialog texts. They belong to a product that is not ours to publish. The fake in [app/adapters/fake_erp.py](../app/adapters/fake_erp.py) has the same shape: screens, functions, dialogs that block, a save message, and a document that can be read back.
