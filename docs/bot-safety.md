# Bot safety

The ERP input bot is the one part of the system that can change data in a system nobody wants broken. So the design does not rely on the bot behaving; it makes the harmful things impossible and makes anything surprising stop the bot.

Each safeguard below says what it prevents, how it works, and where it is specified or demonstrated. The specs are in [docs/concepts](concepts/); the fakes are listed in [app/adapters/README.md](../app/adapters/README.md). "Demonstrated" always means "against the invented fakes", never against a real system (see [README](../README.md#what-the-fakes-prove-and-what-they-cannot)).

| # | Safeguard | Concept / fake | Where you can see it run |
|---|---|---|---|
| 1 | Screen allow-list, popups only via a fixed parent and opener | ActionPolicy | Tests only (policy and sync tests) |
| 2 | Allow-list of form functions; print, delete, confirm cannot be called | ActionPolicy | Demo scenario 5 (`print_form` refused, the fake records that it was never called) |
| 3 | Dialog rules: forbidden-word questions rejected, unknown dialogs stop the bot | ActionPolicy + fake viewer | Demo scenario 3 (unknown dialog stops the bot); the forbidden-word rejection in tests |
| 4 | Saving is a double lock; dry run is the default; the same job id never runs twice | ActionPolicy, JobQueue | Demo scenarios 1 (dry run), 2 (save), 5 (each lock alone is a denial), 6 (duplicate send) |
| 5 | Read back and compare; unclear means NEEDS_HUMAN, with no retry | Verification, JobQueue | Demo scenarios 2 (match), 4 (false "Saved." caught), 6 (no retry) |
| 6 | STOP switch; at most one automatic re-login | JobQueue, settings | STOP: demo scenario 6. Re-login: only the limit in settings, the login itself is described, not implemented here |
| 7 | Prices only from a person | Quote | Tests (a line has no way to get a price except the operator's request); demo scenario 1 shows the operator's path |
| 8 | Fault injection with a fake engine | fake viewer | Demo scenarios 3, 4 and 6 |

The demo is `.venv\Scripts\python -m demo` (see the [README](../README.md#how-to-run-it)).

## 1. Screen allow-list

- **Prevents:** the bot wandering into a screen nobody reviewed.
- **How:** the rules file lists the screens the bot may open (4 in the real system). A popup is allowed only when it is opened by a named function from a named parent screen. Everything else is denied.
- **Where:** `ActionPolicy.check_screen(screen, parent?, opener?) -> Allow | Deny(reason)` in [ActionPolicy](concepts/ActionPolicy.md). The sync `RunNextJob` ([syncs](concepts/syncs.md)) asks before every `Open` step. A denied step ends the job as NEEDS_HUMAN and resets the viewer.

## 2. Allow-list of form functions

- **Prevents:** printing, deleting or confirming a document by the bot, ever.
- **How:** the rules map each screen to the functions the bot may call. Anything not listed is refused. There is no "blocked" list that someone has to keep complete; the dangerous functions are simply absent, so there is no way to call them. When the rules are loaded, a function whose name contains a forbidden word is rejected, and every save function must also be in the normal call list.
- **Where:** `ActionPolicy.check_call(screen, fn, allow_save, saving)` and `ActionPolicy.load(rules)`. Only a person changes the rules file.

## 3. Dialog rules

- **Prevents:** the bot clicking away a dialog it does not understand, for example a question that would delete something.
- **How:** after each open or call, the sync asks the viewer for a pending dialog and classifies its text:
  - A question dialog containing a forbidden word is **rejected** (answered "no"), whatever else the rules say.
  - A dialog matching a known rule is accepted or rejected as that rule says, and a rule can apply only while saving or only during one named function.
  - A dialog that matches no rule **stops the bot**.
  - A question dialog is never accepted unless a rule says so for that exact moment.
- **Where:** `ActionPolicy.classify_dialog(text, saving, during?) -> Accept | Reject | Stop(reason)`. The fake viewer can raise dialogs on demand, including ones no rule knows, so each branch can be exercised. The dialog texts in this repo are made up.

## 4. Double lock on saving, dry run by default, never the same job twice

- **Prevents:** an accidental save, and a duplicate document from a job that ran twice.
- **How:**
  - A save function is allowed only when **both** locks are open: the job is allowed to save (`allow_save`, which is the operator's choice per quote and is honoured only when the site-level flag `LEA_FLAG_SAVE` is on) **and** the bot is in its save step (`saving`, true only for the step marked as the save step). Either one alone is a denial.
  - Without the flag every job is a dry run: the bot types everything in, then resets the viewer without saving.
  - `JobQueue.enqueue` refuses a job id it has already seen, in any state. A job that finished is never taken again.
- **Where:** `ActionPolicy.check_call`, the sync `SentQuoteBecomesJob`, [JobQueue](concepts/JobQueue.md). A person who wants a second run sends the quote again, which is a new job id.

## 5. Read back and compare, NEEDS_HUMAN without retry

- **Prevents:** trusting a "saved" message that is wrong, and silently keeping a half-written document.
- **How:** after a save, the bot reads the document back through the same allow-list and gives both sides to `Verification.compare`. Lines are matched by code; a missing, extra or different-quantity line is a mismatch with a reason such as `qty B: 1 != 3`; a price is compared only where the job carried one. A match finishes the job as done. A mismatch, a denial or an unknown dialog finishes it as NEEDS_HUMAN. Nothing puts a finished job back in the queue.
- **Where:** [Verification](concepts/Verification.md), syncs `SavedJobIsReadBack` and `VerificationFinishesJob`. The fake viewer can report "saved" while holding something else, which is the case this safeguard exists for.
- **Errors:** if the viewer itself raises an error, the job ends as `failed` with the error, after a best-effort reset. That too is not retried.

## 6. STOP switch and at most one automatic re-login

- **Prevents:** a bot that cannot be stopped, and an account locked out by repeated failed logins.
- **How:**
  - `JobQueue.stop()` makes `take` return nothing. A job already running is allowed to finish. `resume()` undoes it.
  - If the login drops, one automatic re-login is allowed (`RELOGIN_MAX = 1` in [app/settings.py](../app/settings.py)). If that fails, the bot does not try again until a person does something.
- **Where:** [JobQueue](concepts/JobQueue.md) for STOP. The re-login limit is a policy value in settings; the login procedure itself is described, not implemented here.

## 7. Prices only from a person

- **Prevents:** the bot or the web app inventing a price.
- **How:** the only way a line gets a price is `Quote.set_price`, and the only caller is the sync `OperatorSetsPrice`, which answers an operator request. A line without a price carries none, and the ERP's own price applies. The bot only copies a price a person entered. `Verification` compares a price only where the job had one.
- **Where:** [Quote](concepts/Quote.md), [syncs](concepts/syncs.md).

## 8. Fault injection with a fake engine

- **Prevents:** safeguards that look right but were never exercised.
- **How:** a fake viewer replaces the real form viewer behind the same `ErpViewer` port ([ports.py](../app/adapters/ports.py)), so faults can be injected on purpose ([app/adapters/README.md](../app/adapters/README.md), "Fake behaviour reference"). Three kinds exist and the demo uses them: a dialog that no rule knows (`dialog_on`), a save message that lies, either by storing nothing or by storing something altered (`save_mode`), and an error raised inside a function (`fail_on`). The fake also really performs the dangerous functions if they are ever called, and records them, so a test can show that the list stays empty. Further faults are added the same way.
- **Limit:** this shows that the safeguards react to those faults in the fake. It does not show how a real viewer fails.

## What is a safeguard here and what is only a rule of work

| Kind | Examples | Why it matters |
|---|---|---|
| Built into the shape | Allow-lists, double lock, queue never re-runs a job | Nobody has to remember anything |
| Policy value | Re-login limit, readings needed, restart limits ([app/settings.py](../app/settings.py)) | Changed by a person, in one place |
| Left to people | Final confirmation, printing, deleting, setting prices | The design gives the bot no way to do them |
