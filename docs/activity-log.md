# Activity log

**Problem:** office staff have done the same work with the same tools for decades. A tool that works very differently would meet resistance and make the work uncomfortable. So the automation has to stay close to what staff already do and only take away the manual steps. That needs an accurate picture of how the work is actually done today, in the existing systems, not how anyone remembers it.

**Answer:** a collector on the field PC records a working day from the tools that are already there: the catalog windows, the ERP form viewer's own request log, the phone-number watcher and the print queue. An evening report merges them into one time-ordered timeline and a short summary. Nothing is clicked, typed or changed.

This page describes the real collector (described, not implemented here). Every example row below is made up: invented parts, times, numbers and screen names, in the same style as the fakes in this repository. No product, screen or address names of the real systems appear here.

## Sources

| Source | Where it comes from | What one record is |
|---|---|---|
| Catalog screens | The catalog windows in the browser, read with UI Automation like the [screen watcher](screen-watcher.md) | One record each time a screen's text has settled (the same text in two readings a second apart). Also: which catalog window came to the front or went behind, a login screen (its text is not read), a window closed. |
| ERP requests | The log that the ERP's form viewer already writes for every request to the ERP server: time, address, sent values, answer | One record per request. Nothing extra runs for this; the report reads the day's viewer logs in the evening. |
| Phone calls | The daily file of the phone-number watcher | One record per state change: ring, answered, ended, missed. |
| Printing and fax | Windows print queue, through the spooler's change notifications; the fax send dialog while it is open | A job entering the queue and leaving it (pages, seconds in the queue, the states it went through). For the fax dialog: which tab is shown, the recipient list or the typed recipient, and whether "store sent image" is on. |
| Print-path windows | Visible windows of the browser that hosts the ERP and of the Windows print host | Title, window class, program, seconds open. Other programs are not looked at. |
| Claim site | A second web site that the ERP opens for one kind of claim | Read the same way as the catalog; login screens are skipped. |

## What a record holds

There is no single event table. Each source keeps its own JSONL file per day, and every record has a time `t`. The report merges them.

Catalog record (`catalog.jsonl` here; invented values):

```json
{"v":1,"t":"2026-03-02T09:12:31.204","ev":"page","win":3,"browser":"edge",
 "title":"Vehicle info","url":"https://catalog.example/vehicle/info",
 "fg":true,"stable":true,"len":1840,"text":"Vehicle info ... TESTVIN0000000017 ..."}
```

| Field | Meaning |
|---|---|
| `ev` | `page`, `focus`, `blur`, `login`, `close`, `leave` |
| `win` | Window number, so several catalog windows open at once stay apart |
| `fg` | Whether the window was in front |
| `stable` | Whether the text had settled when it was recorded |
| `len`, `text` | Length and full text of the screen |

ERP request record (`erp.jsonl` here; invented values):

```json
{"t":"2026-03-02T09:14:10","seq":412,"file":"viewer-09-02-11.log","path":"/part/lookup.do",
 "screen":"Part lookup","noise":false,"ms":180,
 "params":{"PART_NO":"P-100"},"grids":{},"rows":2,"hint":"PART_NO=P-100 PART_NM=Brake pad"}
```

| Field | Meaning |
|---|---|
| `t` | From the answer's `Date` header, in local time |
| `path` | The address the request went to |
| `screen` | Screen name looked up from the address. An address used by several screens gets the screen of the request just before it in the same viewer log. This is a best guess. |
| `noise` | Clock and session checks that every screen sends on its own. Kept, but left out of the timeline and the counts. |
| `params`, `grids` | Sent values, URL-decoded; table data is unpacked into rows |
| `rows`, `hint` | Number of rows in the answer, and up to three named values from it |
| `resp` | The answer, cut at 300,000 characters. A large answer that is the same as an earlier one from the same address is stored once; later records point to the first. |

Phone record: `detected_at`, `state` (`ring`, `answered`, `ended`, `missed`, `other`), `caller`, `call_id`.

Print record: `ev` is `job` (entered the queue) or `done` (left it), with printer, document name, pages, seconds in the queue and `status`, the list of states the job went through. `Printed` in that list means it went out; `Deleted` without `Printed` means it was cancelled.

## From one day to a timeline

The collector runs Monday to Saturday from 08:30 to 19:30 as a scheduled task, without a window and with normal user rights. At 19:30 the report:

1. Reads the day's viewer logs and writes one ERP record per request.
2. Merges catalog, claim site, ERP, print and phone records into `timeline.txt`, ordered by time. Records in the same second keep a fixed source order.
3. Writes `summary.txt`: ERP requests per hour, per screen and per address; requests whose address looks like a save, update or delete; catalog records per screen; print jobs printed and not printed; rings and answered calls.
4. Copies the day's files to a private repository.

A made-up stretch of a timeline (labels shortened, every value invented):

```text
09:12:04  CALL  ring 555-0101 (c-0412)
09:12:09  CALL  answered 555-0101 (c-0412)
09:12:31  CAT   [Vehicle info] /vehicle/info  1840 chars, VIN TESTVIN0000000017, part numbers 0 (front)
09:13:02  CAT   [Group items] /group/items  5120 chars, VIN TESTVIN0000000017, part numbers 14 (front)
09:14:10  ERP   [Part lookup] /part/lookup.do  PART_NO=P-100  -> 2 rows PART_NO=P-100 PART_NM=Brake pad
09:14:52  ERP   [Quote entry] /quote/save.do  CUSTOMER=C-01 | P-100 x2 | P-101 x1  -> 1 rows RESULT=OK
09:15:20  PRINT [paper printer] Quote
09:15:21  PRINT done [paper printer] Quote  1 pages, 0.9 s in the queue
```

Read top to bottom, this is one way a piece of work can look in the existing tools: a call, a vehicle and a part group in the catalog, a lookup and a save in the ERP, a printout. The timeline shows the order and the gaps between steps.

## Cases

A case is one phone call, from the ring to the quote saved in the ERP: the call and the catalog and ERP records in between. Each call is handled right away, because more orders keep coming in. The evening report does not group records into cases yet; today the timeline is read as it is. The grouping below is planned, not built:

| Rule | Why |
|---|---|
| A case starts with a call and ends with the quote saved in the ERP; the call's `call_id` is its key | The work starts with a call, and the save is the step that finishes it. |
| Records from 10 s before the ring to 10 min after hang-up join that call; if two calls match, the most recent one | The same window the live system already uses to attach a catalog identifier to a call ([Call](concepts/Call.md), `CALL_BEFORE` and `CALL_AFTER` in [app/settings.py](../app/settings.py)). |
| The vehicle seen in the case (VIN and model) is kept on it, as a link to other cases | Orders for the same car can keep coming in over several calls. Each call stays its own case; the vehicle shows which cases are about the same car. |
| A record that shows a different vehicle from the one already on the case is not added to it | Two calls close together can be about different cars. A wrong grouping is worse than none. |

## Older logs

The form viewer has kept its request logs on the field PC since March 2022: 7,508 files, about 35 GB. Two batch tools read them, outside office hours only:

| Tool | What it keeps |
|---|---|
| Save history | Every request whose address looks like a write (save, update, delete), with its sent values, and the work before it in the same viewer window since that window's previous write: number of requests, wall time, and active time with gaps over 120 s cut out. That is roughly the effort of one task. Plus tables per month, per address and per day (first request, last request, active minutes, writes). |
| Part lookups | Part lookups that returned more than one row, or where a variant was picked. These show which variant staff chose when one part number has several. |

## What is left out

| Limit | Why |
|---|---|
| No time in other programs is recorded, not even the name of the program in front | The question is how the work goes in the catalog and the ERP, not what else happens at the desk. |
| Login screens are never read; on the claim site, a screen with a password field is recorded only as `login` | That is where secrets are typed. |
| Customer details that appear on screen (names, vehicle numbers, phone numbers) stay in the office's private records only; none of them is in this repository | They are part of the work being looked at, so they are kept there. |
| Session cookies and values that look like passwords are replaced with `<removed>` before a day's files leave the field PC | They are not needed for anything here. |
| In the fax dialog, the subaddress and password fields are not read | Same reason. |
| Other web sites' text is not read; a browser window's address is checked in memory only, to decide whether it is a catalog window | Only the catalog and the claim site are of interest. |
| Records before 08:30 are left out of the report and of the copy | The PC is used remotely before then, which would mix someone else's use into the day. |

## What the log is used for

- Seeing in which order staff look things up in the catalog and enter them in the ERP, so that the quote web app and the bot follow the same order instead of a new one.
- Finding candidates for automation: which ERP tasks take many requests and much time, from the save history.
- Comparing the bot's choice, when one part number has several variants, with what staff chose in the past.
- Following one printed document to the fax dialog: what was printed just before, whether the fax was sent or cancelled, and whether the recipient matches the fax number stored in the ERP for that customer.
- Planned, not done yet: which parts were looked up but not ordered, and how often a quote turns into an order.

## What the log changed

These are changes to the real system that started from something seen in the recorded days or in the older logs. Each row says what the records showed and what was changed. The date is the day the change went into use. Details that would identify customers, vehicles or business volume are left out.

| Date | What the records showed | What was changed |
|---|---|---|
| 2026-10-15 | A vehicle looked up in the catalog during one customer's call also ended up in the quote of a second customer, whose call had ended a few minutes earlier. One lookup fell within two calls. | Before a quote goes to the ERP, the web app asks the operator to confirm the customer when the same vehicle already went to a different customer that day, or when the lookup fell within more than one call. It asks; it does not block. |
| 2026-10-17 | A maintenance set listed one idler pulley. Staff wrote "two pulleys needed" in the memo of two quotes and added the second pulley by hand to a quote the bot had made. The catalog shows two positions for that part in the same group. | A set item that has two positions in one catalog group becomes one line per position. |
| 2026-10-19 | Accident quotes kept growing after they were first saved: staff opened the same quote again and again and added lines while the customer called back with more parts. The web app could only make new quotes. | A quote the bot saved can be opened again in the web app, changed and sent back; the bot changes the same ERP document. |
| 2026-10-19 | In the older logs, when a claim form was saved a second time after the claim site, the only field that changed was most often the adjuster's phone number, which had been empty before. The date fields mostly followed two rules: the date of the first sales document, and today. | The claim window has a phone field that remembers the number per adjuster, the bot fills it in the form, and the dates are filled by those two rules. |
| 2026-10-22 | On one day, both vehicles with a claim had two sales documents each. The bot claimed only one of them; staff merged the two by hand in the ERP. | One claim can cover several sales documents of the same vehicle. |
| 2026-10-22 | Several bot quotes had an empty vehicle-registration field. All of them had been started from a VIN, and the catalog data already held the registration for each of those VINs. | When a quote starts from a VIN, the registration is filled from the catalog data. |
| 2026-10-24 | Staff rarely open the catalog's vehicle-info screen. They pick the model on the parts-group screen and type the last six characters of the VIN. The screen watcher read only the vehicle-info screen, so on the first recorded day it missed more than half of the vehicles looked up, among them the largest quote of the day. | The watcher also reads the parts-group screen. The server accepts a vehicle from it only when exactly one vehicle of that model matches the six characters and the colour, year and engine shown on the screen. The first days in use are still being checked. |
| 2026-10-24 | The bot stopped whenever the ERP listed one part number under two supply sources. On some quotes this meant sending the same lines again and again. The older part-lookup logs held the sources staff had picked in the past. | A rule picks the source, checked against the staff's past choices. Lines the rule could not decide were left out of the save and offered to the operator in a small window. Replaced the next day; see below. |

## What the log did not show

The source rule in the last row was built from the logs, and lines it could not decide went to the operator. On the day it went into use, staff asked for no pick-list windows at all, because they check every quote in the ERP afterwards anyway. Since 2026-10-25 the bot always picks: a source with stock first, and parts with no stock in any source are listed in the quote memo.

The records show what staff did, not what they wanted. Some things only came out once a change was in use and staff could say what bothered them. That is why the web app has a suggestion box, and each suggestion gets a number and is handled one at a time.

## Pitfalls

| Pitfall | What happened | What was done |
|---|---|---|
| Polling the print queue misses jobs | The first version read the queue every 2 seconds. Most jobs stay in the queue for less than a second and a half, so many were never seen. In a test with 16 jobs, the old code recorded 4. | The collector now waits for the spooler's change notifications, which carry the job's details, so a job that disappears at once is still recorded: 16 of 16 in the same test. Every hour it compares its count with the spooler's own job counter and writes `MISSED n` if they differ. |
| The fax dialog opens on the tab last used for sending | The collector read only the recipient-list tab. A fax sent by typing the number on the other tab looked like a dialog without a recipient, and the next dialog opened on the typed tab, where the list did not exist. | Both tabs are read, and the record says which one was shown. |
| The same request twice in the same second | Some ERP screens really send a request twice. | Kept as it is, not removed as a duplicate. |
| The screen name is a guess | Some addresses are used by several screens. | The guess is marked as one in the summary ("best guess from the address"). |

## Cost on the field PC

About 2 % of one CPU core, most of it for reading open catalog windows, and about 100 to 140 MB of memory. With no printing going on, the print-notification thread only waits.

## Mapping to this repository

| Real thing | Here |
|---|---|
| Collector, evening report, older-log tools | Described, not implemented here |
| Catalog reading | Same reading rules as the [screen watcher](screen-watcher.md); modelled by the `ScreenText` port and the `ScriptedScreen` fake |
| Phone records | Same source as the phone-number watcher; modelled by the [Call](concepts/Call.md) concept and the scripted phone fake |
| ERP request log | Written by the form viewer itself; see [legacy-viewer.md](legacy-viewer.md) for that viewer |
