# Operations

How changes reach the real site, and how the site looks after itself. Apart from the flag reader (`app/flags.py`) and the policy values (`app/settings.py`), the scripts and buttons on this page are **described, not implemented here**: they belong to the real deployment, which is not part of this repository.

## Feature flags

Every replaceable piece sits behind a flag (Let It Slop: a new module version is written next to the old one).

| Rule | Detail |
|---|---|
| Naming | `<PREFIX>_FLAG_<MODULE>_V<N>`, for example `APP_FLAG_<MODULE>_V<N>` in the general scheme. In this repository the prefix is `LEA_FLAG_`. |
| Reading | One place reads flags: `app/flags.py`. `LEA_FLAG_<NAME>=1` turns a flag on; anything else is off. |
| Default | Off. A flag that is off means the current code runs exactly as before. |
| Where flags are read | Only in `app/syncs`, never inside a concept. |
| Example in this repo | `LEA_FLAG_SAVE`: without it every job is a dry run ([bot-safety.md](bot-safety.md), safeguard 4). |
| Example of the scheme (invented) | `LEA_FLAG_QUOTE_V2` would switch from the first to the second version of a Quote module. |

## Rollout order

| Stage | What runs | When |
|---|---|---|
| 1. UI test | Automated clicks through the web app against seeded demo data | Any time |
| 2. Demo | The demo site, with fakes in place of the real systems | Any time |
| 3. Real | The flag is turned on at the real site | Outside business hours only |

If a screen-side module fails after its flag is turned on, the screen falls back to the old code rather than showing nothing. When a new version has run quietly for a while on the real site, deleting the old version and its flag is proposed and confirmed with a person first.

## Deploy and updates

| Action | What it does |
|---|---|
| Deploy button | Publishes the current code to the server and shows patch notes: a short plain-language list of what changed, so the operator sees what is different. |
| Check update | Reports whether an update is available; changes nothing. |
| Apply update | Sets STOP on the queue, waits for the job that is running to finish (the bot is never interrupted mid-job), applies the update, then resumes. See [JobQueue](concepts/JobQueue.md): `stop()` lets a running job finish. |

## Self-healing

| Mechanism | Rule |
|---|---|
| Health check | Every 3 minutes the site is asked twice, a short time apart. If neither answers, it counts as down. |
| Restart | Restart **only the site**. Anything that involves a login (the form viewer session, the bot, the catalog session) is never restarted automatically, because that would mean logging in without a person. |
| Crash-loop stop | Restarting stops after 3 restarts in a row that did not bring the site back by the next check, or after 4 restarts within one hour (the site comes up and dies again and again). The values are `RESTART_MAX_IN_A_ROW = 3` and `RESTART_MAX_PER_HOUR = 4` in [app/settings.py](../app/settings.py). After the stop it only writes one log line per hour. It starts working again when the site answers again (a person pressed Restore) or after a reboot. |
| Standing aside | The self-check does nothing while Restore or Turn everything off is running (those take over), right after a boot, or while a pause marker file exists. |
| Login | At most one automatic re-login (`RELOGIN_MAX = 1`), so retries cannot lock an account. |

The reason for the crash-loop stop is to prevent endless switching on and off: a site that dies again right after each restart is not helped by a further restart, so the self-check stops and leaves it to a person.

## Two buttons for a bad day

Both live on the server's desktop and are for administering the server, which runs the whole system on one machine. They do not touch feature flags. The emergency they exist for is that the operator cannot use the quote site.

| Button | Meaning |
|---|---|
| Restore | Brings the server back to its known initial configuration, whatever state it is in (switched off, half broken): the scheduled tasks are registered exactly as intended, the site and the demo answer, the private-network sharing is as expected, the form viewer session and the catalog session are open, and the bot queue is running (STOP removed, and at most one automatic re-login if the session dropped). Parts that are already right are left alone, so it can be pressed repeatedly. It ends with a colour-coded summary of what was fine, what it fixed, and what still fails. |
| Turn everything off | A reset: stops everything this system runs on the server (the bot, the site, the demo) by finding the actual processes, not by trusting task state. If quotes are waiting it asks for explicit confirmation first, and a plain Enter cancels without changing anything. The self-check and the receiver for the field PC's restore button are left running, so the self-check starts the site again within 3 minutes unless a pause marker is set. |

When something is tangled (running but not working), the order is: turn everything off, then restore. The same order is used to start fresh after code has been updated.

## Real-environment test table

Tests against a real site are written down as a table, one row per step:

| Step | Procedure | Command | Pass criterion | Result (date) |
|---|---|---|---|---|

- **Step**: a number, so a result can be cited.
- **Procedure**: what a person does, in a sentence.
- **Command**: the exact command or button, so the step can be repeated.
- **Pass criterion**: what must be seen, written before the test is run.
- **Result (date)**: pass or fail, with the date it was last run. A row without a result is not a pass.

Items that could not be checked are kept in a **separate list of unverified items**, not left out and not marked as passed.

Example (all rows invented, for the format only):

| Step | Procedure | Command | Pass criterion | Result (date) |
|---|---|---|---|---|
| 1 | Send a quote with the save flag off | `send-quote --id example-1` | Job ends as done; no document exists in the ERP | pass (date) |
| 2 | Send the same quote again | `send-quote --id example-1` | The queue keeps one job; nothing runs twice | pass (date) |
| 3 | Set STOP, then send a quote | `queue stop`, `send-quote --id example-2` | Job stays queued until resume | fail (date) |
| 4 | Drop the login on purpose | `session drop` | One re-login, then the job runs | not yet run |

Unverified items (invented):

- Behaviour after a power cut in the middle of a job.
- Behaviour when the catalog system is slow for a long time.

## What the fakes cannot show here

Nothing here was run from this repository. The fakes can show that a flag-off job is a dry run or that STOP holds the queue; they cannot show that a real update, restart or restore works.
