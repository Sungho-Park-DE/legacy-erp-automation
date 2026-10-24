# Decision log

The decisions that shaped the real system, in the order they were made, with one sentence of reason. Where no reason was written down in the material this log is based on, the row says "reason not recorded" instead of guessing. The other documents say how the decisions show up in the design: [architecture](architecture.md), [bot safety](bot-safety.md), [screen watcher](screen-watcher.md), [operations](operations.md).

| # | Decision | Reason |
|---|---|---|
| 1 | Final submission, printing and deleting are done only by a person. The robot must not get in the way of use of the field PC. | The field PC is the operator's working machine, so automation must not take it over; why final submission, printing and deleting stay with a person is not recorded beyond the principle that a person keeps every decision that matters. |
| 2 | Client and server. Reading goes through the browser's DOM; writing starts as a keyboard macro. | The heavy work runs on one server and the field PC is only used through a browser; writing started as a keyboard macro because the ERP's form viewer is an ActiveX control. |
| 3 | No language model at run time in the first version. | The core path can be done with rules, and the one remaining candidate for a model was too rare to be worth building. |
| 4 | Switch to scripting the form viewer through COM. The keyboard and screen-coordinate bot is deleted. First real save and first real use. | The viewer turned out to have a scripting interface that can be called from outside (set values, call form functions, read the screen data as XML), and dry-run and save tests passed with it. |
| 5 | A resident watcher on the field PC, and self-healing. | The phone program's log and the catalog screen are on the field PC, which is where the watchers have to run. Self-healing: the emergency that matters is the operator being unable to use the quote site, so the server restarts the site by itself, and a button on the field PC can restore the server. |
| 6 | The input-only virtual machine is dropped; one server does the job. | It was no longer in use; further reason not recorded. |
| 7 | The bot copies only prices that a person entered. | The owner wanted prices to stay a person's call (the Quote concept: only a person ever sets a price); the bot is not to decide them. |

## How to read these rows

- The first, fourth and last rows are the ones the design depends on most: what a person keeps, how the bot talks to the ERP, and where a price comes from. They appear again as [ActionPolicy](concepts/ActionPolicy.md), the `ErpViewer` port in [ports.py](../app/adapters/ports.py), and [Quote](concepts/Quote.md).
- Reasons are one sentence each and are summaries, not quotations. Where no reason was written down, the row says so instead of inventing one.
