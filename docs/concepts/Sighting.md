# Concept: Sighting

**Purpose:** Decide that the operator really has an identifier on screen, without guessing and without repeating, from screen text that flickers while it loads.

**Operational principle:** If the screen shows identifier `A` once, nothing is confirmed yet; if the next reading shows `A` again, `A` is confirmed once; further readings of `A` within the quiet period confirm nothing; if a reading shows `A` and `B` and neither is selected, nothing is confirmed and the run of `A`s starts over.

**State:**
- last: str?            the candidate of the previous reading
- streak: int           how many readings in a row showed `last`
- sent: str -> datetime when each identifier was last confirmed

**Actions:**
- observe(candidates: list str, selected: str?, at, needed: int, quiet: timedelta) -> Confirmed(id) | Pending | Ambiguous | Repeated
  - effects:
    - the reading's candidate is `selected` if given, else the only candidate; with no candidate the streak resets (Pending); with several and none selected the streak resets (Ambiguous)
    - same candidate as `last` increases the streak, a different one starts a new streak of 1
    - when the streak reaches `needed`: if the identifier was confirmed less than `quiet` ago the result is Repeated, otherwise Confirmed and `sent[id] = at`

**Queries:**
- last_confirmed(id) -> datetime?

**Not this concept's job:** reading the screen and finding candidates in its text (adapter `screen`), which call the identifier belongs to (Call, via a sync), the numbers `needed` and `quiet` (settings).
