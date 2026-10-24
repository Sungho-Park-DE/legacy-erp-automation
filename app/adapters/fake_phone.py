"""A phone log that plays back a fixed list of events, each exactly once."""
from __future__ import annotations

from collections.abc import Iterable

from app.adapters.ports import PhoneEvent


class ScriptedPhone:
    def __init__(self, events: Iterable[PhoneEvent]):
        self._events = list(events)
        self._next = 0

    def poll(self) -> list[PhoneEvent]:
        fresh = self._events[self._next:]
        self._next = len(self._events)
        return fresh
