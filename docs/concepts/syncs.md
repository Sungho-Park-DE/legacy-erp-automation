# Syncs

Implemented in `app/syncs/`, one function per sync. `Request.*` are operator actions; `Phone.*`, `Screen.*` and `Erp.*` are adapter calls (`app/adapters`).

## Calls and screen

```text
sync RingStartsCall
  when   Phone.ring(number, at)
  then   Call.ring(number, at)

sync HangUpEndsCall
  when   Phone.hang_up(number, at)
  where  Call.recent() has an open call from number = c
  then   Call.hang_up(c, at)

sync ScreenReadingIsObserved
  when   Screen.read() -> { candidates, selected, at }
  then   Sighting.observe(candidates, selected, at, settings.SIGHTING_NEEDED, settings.SIGHTING_QUIET)

sync ConfirmedSightingJoinsCall
  when   Sighting.observe(...) -> Confirmed(id)
  then   Call.attach(id, at, settings.CALL_BEFORE, settings.CALL_AFTER)
```

## Quote to queue

```text
sync OperatorAddsCatalogLine
  when   Request.add_line(quote, identifier, qty)
  where  Catalog.lookup(identifier) -> rows
  then   Quote.add_line(quote, row.code, row.name, qty) for each chosen row

sync OperatorSetsPrice
  when   Request.set_price(quote, line, price)
  then   Quote.set_price(quote, line, price)

sync SentQuoteBecomesJob
  when   Request.send(quote, save: bool)
  then   lines := Quote.send(quote)
         JobQueue.enqueue(job = quote, payload = { lines, save })
```

`save` is the operator's choice per quote and is honoured only when flag `SAVE` is on; otherwise every job is a dry run. The flag is checked twice, when the job is queued and again when it runs; a flag that was switched off in between turns the save step into a Deny, which ends the job as NEEDS_HUMAN.

Sending the same quote twice never reaches the queue: `Quote.send` refuses a quote that was already sent. `JobQueue.enqueue` is a second guard for a job id it already knows.

## Running a job

```text
sync RunNextJob
  when   worker tick
  where  JobQueue.take() -> (job, payload)
  then   steps := ErpRecipe.steps(payload)            # adapter side: screens, fields, functions
         for each step:
           Open(screen)     -> ActionPolicy.check_screen  -> Allow ? Erp.open_screen   : stop
           Set(path, value) -> (no check; values only go into an allowed screen)
           Call(fn)         -> ActionPolicy.check_call(screen, fn, payload.save and flag SAVE, saving = step.is_save)
                                                        -> Allow ? Erp.call            : stop
           after each Open/Call: while Erp.pending_dialog() -> text:
                                 ActionPolicy.classify_dialog(text, saving, during = fn)
                                 Accept -> Erp.answer_dialog(True); Reject -> Erp.answer_dialog(False); Stop -> stop
         dry run: Erp.reset() after the last step, outcome done
         stop (Deny or Stop) -> Erp.reset(); JobQueue.finish(job, needs_human, reason)
         saved job: no reset; the read back below decides the outcome

sync SavedJobIsReadBack
  when   RunNextJob saved job
  then   actual := Erp.read_back(job)                 # through allowed screens only, same checks as above
         Verification.compare(job, expected = payload, actual)

sync VerificationFinishesJob
  when   Verification.compare(job, ...) -> Match            then JobQueue.finish(job, done)
  when   Verification.compare(job, ...) -> Mismatch(r)      then JobQueue.finish(job, needs_human, r)

sync AdapterErrorFinishesJob
  when   any Erp.* raises
  then   Erp.reset() (best effort); JobQueue.finish(job, failed, error)
```

No sync retries a job. A person re-sends, which is a new job id.

## Interrupted jobs and the save journal

```text
sync SaveIsJournaled
  when   RunNextJob reaches a step Call(fn, is_save = true) that ActionPolicy allowed
  where  SaveJournal.phase(job) = none          # else stop: needs_human "save already attempted"
  then   SaveJournal.mark_saving(job, payload.lines, known_before)   # before Erp.call(fn)

sync ReadBackIsJournaled
  when   SavedJobIsReadBack found document ref
  then   SaveJournal.mark_read_back(job, ref)

sync RecoverInterruptedJob
  when   worker start
  where  JobQueue.list(running) -> job          # a job the previous worker never finished
  then   SaveJournal.phase(job) is saving or read_back -> SavedJobIsReadBack(job)   # read only, never typed again
         SaveJournal.phase(job) is none -> Erp.reset(); JobQueue.finish(job, needs_human, "interrupted before saving")
```

`known_before` is the set of document refs on the list screen before the save, read only when flag `VERIFICATION_V2` is on (empty otherwise). With that flag on, `SavedJobIsReadBack` lists documents, asks `Verification.locate(job, documents, known_before)`, and only a `Found(ref)` goes on to `compare`; `NotFound` and `Many` end the job as needs_human.

## Changing a saved document

```text
sync EditBecomesJob
  when   Request.edit(job_of, lines)
  where  SaveJournal.saved_lines(job_of) = base and SaveJournal.saved_ref(job_of) = ref
  then   JobQueue.enqueue(edit_job, payload = { mode: edit, of: job_of, ref, base, lines, save: true })

sync RunEditJob
  when   JobQueue.take() -> (job, payload with mode edit)
  then   current := Erp.read_back(ref) through ErpRecipe.read_back_steps     # allowed screens only
         Revision.plan(base, current, lines) -> Stop(r) ? needs_human r
         mark := len(Erp.request_log())
         steps := ErpRecipe.edit_steps(ref, ops), run like RunNextJob (same ActionPolicy checks, journal before the save step)
         a dialog accepted by ActionPolicy while fn = remove_line is answered true only if
           Revision.may_confirm_removal(ErpRecipe.item_in_dialog(text), item being removed); else answered false and stop
         Revision.check_requests(Erp.request_log()[mark:], settings.EDIT_UPDATE_REQUEST, settings.EDIT_DANGEROUS_REQUESTS) -> Stop(r) ? needs_human r
         read back and Verification.compare(expected = lines)
```

An edit is a new job id; the original job is never re-run.
