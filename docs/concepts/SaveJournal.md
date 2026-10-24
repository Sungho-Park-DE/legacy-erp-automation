# Concept: SaveJournal

**Purpose:** Remember, before the save button is pressed, that the bot is about to save a job, so that a bot that died half-way never types and saves the same job again after a restart.

**Operational principle:** If the bot marks job J as saving and then dies, then after the restart `phase(J)` is `saving`, so the job is only read back and never typed or saved again; marking J as saving a second time is refused.

**State:**
- entries: JobId -> { phase: saving | read_back, lines: list Line, known_before: set str, ref: str? }
- Line = { code: str, qty: int, price: decimal? }

**Actions:**
- mark_saving(job, lines, known_before) 
  - requires: no entry for job (otherwise `AlreadySaving`)
  - effects: entries[job] = { saving, lines, known_before, ref: none }
- mark_read_back(job, ref)
  - requires: an entry for job (otherwise `UnknownJob`)
  - effects: phase = read_back, ref = ref (the document the read back found)

**Queries:**
- phase(job) -> saving | read_back | none
- saved_lines(job) -> list Line? (what the bot meant to save)
- known_before(job) -> set str? (document refs that existed before the save)
- saved_ref(job) -> str?

**Precondition for "no entry means nothing was saved":** the entry is written durably before the save function is called. An in-memory journal that is lost with the process cannot tell "never saved" from "journal gone".

**Not this concept's job:** storing itself on disk (the real system keeps it in a file next to the queue; the demo keeps it in memory and reuses it across a simulated restart), deciding what to do with an interrupted job (sync `RecoverInterruptedJob`).
