"""Screen text that plays back a script of readings, plus a helper that builds a flickering load."""
from __future__ import annotations

from collections.abc import Iterable
from datetime import datetime, timedelta

from app.adapters.ports import ScreenReading


class ScriptedScreen:
    def __init__(self, readings: Iterable[ScreenReading]):
        self._readings = list(readings)
        self._next = 0

    def read(self) -> ScreenReading | None:
        if self._next >= len(self._readings):
            return None
        reading = self._readings[self._next]
        self._next += 1
        return reading


def flicker(
    identifier: str,
    start: datetime,
    step: timedelta,
    partial: tuple[str, ...] | None = None,
    settle_readings: int = 3,
    noise: str | None = None,
) -> list[ScreenReading]:
    """Readings of a screen that is still loading, one per `step` from `start`.

    First one reading with no candidate, then one reading per `partial` text (default: the first half of
    the identifier), then `settle_readings` readings showing `identifier`. With `noise`, the settled readings
    show `noise` as a second candidate and nothing selected (ambiguous).
    """
    texts = (identifier[: len(identifier) // 2],) if partial is None else partial
    shown: list[tuple[list[str], str | None]] = [([], None)]
    shown += [([text], None) for text in texts]
    if noise is None:
        shown += [([identifier], None)] * settle_readings
    else:
        shown += [([identifier, noise], None)] * settle_readings
    return [ScreenReading(at=start + step * i, candidates=list(c), selected=s) for i, (c, s) in enumerate(shown)]
