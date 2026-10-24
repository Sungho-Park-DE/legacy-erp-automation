from dataclasses import dataclass
from datetime import datetime, timedelta


@dataclass(frozen=True)
class Confirmed:
    id: str


@dataclass(frozen=True)
class Pending:
    pass


@dataclass(frozen=True)
class Ambiguous:
    pass


@dataclass(frozen=True)
class Repeated:
    pass


Result = Confirmed | Pending | Ambiguous | Repeated


class Sighting:
    def __init__(self) -> None:
        self._last: str | None = None
        self._streak = 0
        self._sent: dict[str, datetime] = {}

    def observe(
        self,
        candidates: list[str],
        selected: str | None,
        at: datetime,
        needed: int,
        quiet: timedelta,
    ) -> Result:
        if needed < 1:
            raise ValueError("needed must be at least 1")

        if selected is not None:
            candidate = selected
        else:
            distinct = list(dict.fromkeys(candidates))
            if not distinct:
                self._reset()
                return Pending()
            if len(distinct) > 1:
                self._reset()
                return Ambiguous()
            candidate = distinct[0]

        if candidate == self._last:
            self._streak += 1
        else:
            self._last = candidate
            self._streak = 1

        if self._streak < needed:
            return Pending()

        sent_at = self._sent.get(candidate)
        if sent_at is not None and at - sent_at < quiet:
            return Repeated()
        self._sent[candidate] = at
        return Confirmed(candidate)

    def last_confirmed(self, id: str) -> datetime | None:
        return self._sent.get(id)

    def _reset(self) -> None:
        self._last = None
        self._streak = 0
