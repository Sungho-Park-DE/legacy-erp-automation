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
