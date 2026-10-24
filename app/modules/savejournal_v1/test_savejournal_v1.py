from decimal import Decimal

import pytest

from app.modules.savejournal_v1 import AlreadySaving, SaveJournal, SaveJournalError, UnknownJob

LINES = [{"code": "A1", "qty": 2, "price": Decimal("1.50")}, {"code": "B2", "qty": 1, "price": None}]


def test_operational_principle_crash_after_mark_saving():
    j = SaveJournal()
    j.mark_saving("J", LINES, {"R1"})
    # simulated restart: the same instance is reused
    assert j.phase("J") == "saving"
    assert j.saved_lines("J") == LINES
    assert j.known_before("J") == frozenset({"R1"})
    assert j.saved_ref("J") is None
    with pytest.raises(AlreadySaving):
        j.mark_saving("J", LINES, set())


def test_read_back_sets_phase_and_ref_and_can_repeat():
    j = SaveJournal()
    j.mark_saving("J", LINES, set())
    j.mark_read_back("J", "R2")
    assert (j.phase("J"), j.saved_ref("J")) == ("read_back", "R2")
    j.mark_read_back("J", "R3")
    assert (j.phase("J"), j.saved_ref("J")) == ("read_back", "R3")
    with pytest.raises(AlreadySaving):
        j.mark_saving("J", LINES, set())


def test_unknown_job():
    j = SaveJournal()
    with pytest.raises(UnknownJob):
        j.mark_read_back("X", "R")
    assert j.phase("X") is None
    assert j.saved_lines("X") is None
    assert j.known_before("X") is None
    assert j.saved_ref("X") is None


def test_errors_are_value_errors():
    assert issubclass(AlreadySaving, SaveJournalError)
    assert issubclass(UnknownJob, SaveJournalError)
    assert issubclass(SaveJournalError, ValueError)


def test_stores_and_returns_copies():
    j = SaveJournal()
    lines = [dict(line) for line in LINES]
    known = {"R1"}
    j.mark_saving("J", lines, known)
    lines[0]["qty"] = 99
    lines.append({"code": "C", "qty": 1, "price": None})
    known.add("R9")
    assert j.saved_lines("J") == LINES
    assert j.known_before("J") == frozenset({"R1"})
    out = j.saved_lines("J")
    out[0]["qty"] = 7
    out.clear()
    assert j.saved_lines("J") == LINES
