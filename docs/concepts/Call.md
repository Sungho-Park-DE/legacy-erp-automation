# Concept: Call [Item]

**Purpose:** Keep track of the phone calls coming in, so that what the operator looks up during a call ends up next to that call.

**Operational principle:** If a call rings at 10:00:00 and is hung up at 10:03:00, then an item seen at 10:02:00 is attached to that call, an item seen at 09:59:55 is attached too (it was looked up just before the phone rang), and an item seen at 10:30:00 is attached to no call.

**State:**
- calls: CallId -> { number: str, rang_at: datetime, ended_at: datetime?, items: list Item }

**Actions:**
- ring(number, at) -> CallId
  - effects: a new call with no items
- hang_up(call, at)
  - requires: call exists and has not ended
  - effects: ended_at = at
- attach(item, at, before: timedelta, after: timedelta) -> CallId?
  - effects: the item is added to the most recent call with `rang_at - before <= at <= (ended_at or at) + after`; if no call matches, nothing changes and None is returned; an item already on that call is not added twice

**Queries:**
- recent(limit) -> list { call, number, rang_at, ended_at, items }

**Not this concept's job:** reading the phone system (adapter `phone`), deciding that an item was really seen (Sighting), the window sizes (settings, passed in by a sync).
