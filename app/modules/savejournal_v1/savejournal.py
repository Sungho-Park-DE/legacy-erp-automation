import copy
from dataclasses import dataclass, field
from typing import Optional


class SaveJournalError(ValueError):
    pass


class AlreadySaving(SaveJournalError):
    pass


class UnknownJob(SaveJournalError):
    pass


@dataclass
class _Entry:
    phase: str
    lines: list
    known_before: frozenset
    ref: Optional[str] = field(default=None)


class SaveJournal:
    def __init__(self):
        self._entries: dict[str, _Entry] = {}

    def mark_saving(self, job, lines, known_before) -> None:
        if job in self._entries:
            raise AlreadySaving(job)
        self._entries[job] = _Entry(
            "saving", [dict(copy.deepcopy(line)) for line in lines], frozenset(known_before)
        )

    def mark_read_back(self, job, ref) -> None:
        entry = self._entries.get(job)
        if entry is None:
            raise UnknownJob(job)
        entry.phase = "read_back"
        entry.ref = ref

    def phase(self, job) -> Optional[str]:
        entry = self._entries.get(job)
        return entry.phase if entry else None

    def saved_lines(self, job) -> Optional[list]:
        entry = self._entries.get(job)
        return copy.deepcopy(entry.lines) if entry else None

    def known_before(self, job) -> Optional[frozenset]:
        entry = self._entries.get(job)
        return entry.known_before if entry else None

    def saved_ref(self, job) -> Optional[str]:
        entry = self._entries.get(job)
        return entry.ref if entry else None
