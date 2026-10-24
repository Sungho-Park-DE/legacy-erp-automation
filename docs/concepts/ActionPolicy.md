# Concept: ActionPolicy

**Purpose:** Say, before the robot does anything in the target system, whether it is allowed — so that dangerous actions are not just avoided but impossible, and anything unexpected stops the robot instead of being clicked away.

**Operational principle:** If the rules allow screen `Q` and functions `fill_line` and `save`, then opening `Q` and calling `fill_line` are allowed, `print` is refused because it is not listed, and `save` is refused unless saving is both permitted for this job and the robot is in its save step; a dialog asking "Delete this document?" is rejected, a known "Saved." notice is accepted, and a dialog nobody has seen before stops the robot.

**State** (loaded from one rules file; changed only by a person):
- screens: set str
- popups: str -> { parent: str, opener: str }
- calls: str -> set str            screen -> allowed functions
- save_calls: set str              functions that write; allowed only in the save step
- forbidden: list str              words that make any question dialog a rejection
- dialogs: list { pattern, answer: accept | reject, when: always | saving, during: str? }

**Actions:**
- load(rules)
  - requires: every save call is also in `calls`; no forbidden word appears in a function name
- check_screen(screen, parent?, opener?) -> Allow | Deny(reason)
- check_call(screen, fn, allow_save: bool, saving: bool) -> Allow | Deny(reason)
- classify_dialog(text, saving: bool, during: str?) -> Accept | Reject | Stop(reason)
  - effects: none; a question dialog containing a forbidden word is Reject; a dialog matching no rule is Stop; a question dialog is never Accept unless a rule says so for this moment

**Queries:**
- rules() -> the loaded rules, for showing to a person

**Not this concept's job:** doing the action (ERP adapter, called by a sync only after Allow), which steps a job has (ERP recipe), what to do with the job after Deny or Stop (sync -> JobQueue NEEDS_HUMAN).
