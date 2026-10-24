from dataclasses import dataclass, field
from datetime import datetime, timedelta

CallId = int


class UnknownCall(ValueError):
    pass


class CallAlreadyEnded(ValueError):
    pass


@dataclass(frozen=True)
class CallView:
    call: CallId
    number: str
    rang_at: datetime
    ended_at: datetime | None
    items: tuple[str, ...]


@dataclass
class _Call:
    number: str
    rang_at: datetime
    ended_at: datetime | None = None
    items: list[str] = field(default_factory=list)


class Calls:
    def __init__(self) -> None:
        self._calls: dict[CallId, _Call] = {}

    def ring(self, number: str, at: datetime) -> CallId:
        call_id = len(self._calls) + 1
        self._calls[call_id] = _Call(number=number, rang_at=at)
        return call_id

    def hang_up(self, call: CallId, at: datetime) -> None:
        record = self._calls.get(call)
        if record is None:
            raise UnknownCall(call)
        if record.ended_at is not None:
            raise CallAlreadyEnded(call)
        record.ended_at = at

    def attach(
        self, item: str, at: datetime, before: timedelta, after: timedelta
    ) -> CallId | None:
        for call_id in self._most_recent_first():
            record = self._calls[call_id]
            end = at if record.ended_at is None else record.ended_at
            if record.rang_at - before <= at <= end + after:
                if item not in record.items:
                    record.items.append(item)
                return call_id
        return None

    def recent(self, limit: int | None = None) -> list[CallView]:
        if limit is not None and limit < 0:
            raise ValueError("limit must not be negative")
        ids = self._most_recent_first()
        if limit is not None:
            ids = ids[:limit]
        return [self._view(call_id) for call_id in ids]

    def _most_recent_first(self) -> list[CallId]:
        return sorted(
            self._calls, key=lambda i: (self._calls[i].rang_at, i), reverse=True
        )

    def _view(self, call_id: CallId) -> CallView:
        record = self._calls[call_id]
        return CallView(
            call=call_id,
            number=record.number,
            rang_at=record.rang_at,
            ended_at=record.ended_at,
            items=tuple(record.items),
        )
