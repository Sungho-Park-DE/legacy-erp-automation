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
| 8 | Fault injection with a fake engine | fake viewer | Demo scenarios 3, 4, 6, 7, 9 and 10 |
| 9 | A bot that dies mid-save never saves twice | SaveJournal, JobQueue | Demo scenario 7; the refusal of a second save and the job interrupted before saving in tests |
| 10 | Changing a saved document: stop if a person changed it, confirm a removal for one exact item, count the requests sent | Revision, ActionPolicy, SaveJournal | Demo scenarios 8 (change), 9 (a person changed it first), 10 (removal question about another item); the request count and a locked document in tests |

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
- **Version 2, when the ERP numbers its documents:** a target system that gives each saved document its own number leaves the bot a harder question: which document on the list is the one it just saved? Taking the newest one is a guess. Version 2 (`verification_v2`, flag `LEA_FLAG_VERIFICATION_V2`, off by default) lists the document numbers before the save and keeps them in the save journal (safeguard 9). After the save only a document that carries the job's note and was not on the earlier list counts: none or more than one means NEEDS_HUMAN with the candidates named. Lines are compared as a bag of (code, quantity), so the same lines in another order still match and two lines with the same code are counted rather than refused; a line that belongs to another document stops the comparison. Shown in tests only (`tests/syncs/test_syncs_journal_and_edit.py`); the demo runs version 1.

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
- **How:** a fake viewer replaces the real form viewer behind the same `ErpViewer` port ([ports.py](../app/adapters/ports.py)), so faults can be injected on purpose ([app/adapters/README.md](../app/adapters/README.md), "Fake behaviour reference"). These kinds exist: a dialog that no rule knows (`dialog_on`), a save message that lies, either by storing nothing or by storing something altered (`save_mode`), an error raised inside a function (`fail_on`), the bot process dying right after a save went through (`crash_after_save`), a removal question that names another item (`name_in_removal`), an extra request in the viewer's request log (`extra_request`), and a person changing a stored document (`edit_by_person`). The fake also really performs the dangerous functions if they are ever called, and records them, so a test can show that the list stays empty.
- **Limit:** this shows that the safeguards react to those faults in the fake. It does not show how a real viewer fails.

## 9. A bot that dies mid-save never saves twice

- **Prevents:** a second document when the bot dies between pressing save and reading the result back. "Never the same job id twice" (safeguard 4) does not cover this: the job was taken once, and a restarted worker that simply starts it again would type and save it a second time.
- **How:** right before the save function is called, after ActionPolicy allowed it, the sync writes the job into a save journal (`mark_saving`), with the lines it means to save and the document numbers that existed before. After the read back it records which document it found. When a worker starts, it looks for jobs the queue still shows as running:
  - The journal has the job: the save may or may not have gone through, so the job is only read back and compared, never typed again.
  - The journal does not have it: nothing was saved by the bot, the viewer is reset and the job ends as NEEDS_HUMAN ("interrupted before saving"). It is not re-run, in keeping with "no sync retries a job".
  - Marking the same job as saving a second time is refused, so a save step can never run twice for one job.
- **Where:** [SaveJournal](concepts/SaveJournal.md), syncs `SaveIsJournaled`, `ReadBackIsJournaled` and `RecoverInterruptedJob` ([syncs](concepts/syncs.md)). In the real system the journal lives in a file next to the queue; here it is kept in memory and handed to the restarted worker.

## 10. Changing a saved document

- **Prevents:** overwriting what a person changed in the ERP since the bot saved, removing the wrong line, and a change that quietly sent more than one update or a dangerous request.
- **How:**
  - A change is a new job that names the earlier job. What the bot saved then comes from the save journal; a job without a read-back document cannot be changed.
  - Before typing anything, the bot reads the document as it is now. `Revision.plan` compares it with what was saved: different (in any order), missing or locked means stop, and nothing is typed. Otherwise it plans the steps: remove, change quantity, add.
  - Removing a line raises a confirmation in the viewer. The dialog rule accepts it only while the removal function runs (safeguard 3), and on top of that the sync accepts it only when the item the question names is the item being removed. Any other item: the answer is no, and a person decides.
  - Before and after the change the bot reads the viewer's own log of requests sent to the ERP server. Exactly one update and no request on the dangerous list (`delete`, `finalize`, `print`, `save` in [app/settings.py](../app/settings.py)), or the job needs a person. A message on screen can be wrong; the requests that actually left the viewer are harder to fake.
  - The result is read back and compared like any save (safeguard 5).
- **Where:** [Revision](concepts/Revision.md), syncs `EditBecomesJob` and `RunEditJob`, the fake viewer's edit screen and request log ([app/adapters/README.md](../app/adapters/README.md)).
- **Limit:** the bot can remove a line from its own document; it still cannot delete, finalize or print a document.

## What is a safeguard here and what is only a rule of work

| Kind | Examples | Why it matters |
|---|---|---|
| Built into the shape | Allow-lists, double lock, queue never re-runs a job | Nobody has to remember anything |
| Policy value | Re-login limit, readings needed, restart limits ([app/settings.py](../app/settings.py)) | Changed by a person, in one place |
| Left to people | Final confirmation, printing, deleting, setting prices | The design gives the bot no way to do them |
