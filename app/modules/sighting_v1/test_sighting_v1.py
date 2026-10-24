from datetime import datetime, timedelta

import pytest

from app.modules.sighting_v1 import (
    Ambiguous,
    Confirmed,
    Pending,
    Repeated,
    Sighting,
)

NEEDED = 2
QUIET = timedelta(seconds=60)
T0 = datetime(2026, 1, 5, 10, 0, 0)


def t(seconds: int) -> datetime:
    return T0 + timedelta(seconds=seconds)


def observe(s: Sighting, candidates, at, selected=None, needed=NEEDED, quiet=QUIET):
    return s.observe(candidates, selected, at, needed, quiet)


def test_operational_principle():
    s = Sighting()
    assert observe(s, ["A"], t(0)) == Pending()
    assert observe(s, ["A"], t(1)) == Confirmed("A")
    assert observe(s, ["A"], t(2)) == Repeated()
    assert observe(s, ["A", "B"], t(3)) == Ambiguous()
    assert observe(s, ["A"], t(4)) == Pending()
    assert observe(s, ["A"], t(5)) == Repeated()
    assert s.last_confirmed("A") == t(1)


def test_single_reading_confirms_nothing():
    s = Sighting()
    assert observe(s, ["A"], t(0)) == Pending()
    assert s.last_confirmed("A") is None


def test_no_candidate_is_pending_and_resets_the_streak():
    s = Sighting()
    observe(s, ["A"], t(0))
    assert observe(s, [], t(1)) == Pending()
    assert observe(s, ["A"], t(2)) == Pending()
    assert observe(s, ["A"], t(3)) == Confirmed("A")


def test_several_candidates_without_selection_is_ambiguous_and_resets_the_streak():
    s = Sighting()
    observe(s, ["A"], t(0))
    assert observe(s, ["A", "B"], t(1)) == Ambiguous()
    assert observe(s, ["A"], t(2)) == Pending()
    assert observe(s, ["A"], t(3)) == Confirmed("A")


def test_selected_wins_over_several_candidates():
    s = Sighting()
    assert observe(s, ["A", "B"], t(0), selected="B") == Pending()
    assert observe(s, ["A", "B"], t(1), selected="B") == Confirmed("B")
    assert s.last_confirmed("B") == t(1)
    assert s.last_confirmed("A") is None


def test_selected_wins_over_a_single_other_candidate():
    s = Sighting()
    assert observe(s, ["A"], t(0), selected="B") == Pending()
    assert observe(s, ["A"], t(1), selected="B") == Confirmed("B")
    assert s.last_confirmed("A") is None


def test_selected_without_candidates_counts():
    s = Sighting()
    observe(s, [], t(0), selected="A")
    assert observe(s, [], t(1), selected="A") == Confirmed("A")


def test_repeated_candidates_in_one_reading_are_one_candidate():
    s = Sighting()
    observe(s, ["A", "A"], t(0))
    assert observe(s, ["A", "A"], t(1)) == Confirmed("A")


def test_different_candidate_starts_a_new_streak_of_one():
    s = Sighting()
    observe(s, ["A"], t(0))
    assert observe(s, ["B"], t(1)) == Pending()
    assert observe(s, ["A"], t(2)) == Pending()
    assert observe(s, ["A"], t(3)) == Confirmed("A")


def test_streak_keeps_growing_after_confirmation():
    s = Sighting()
    observe(s, ["A"], t(0))
    observe(s, ["A"], t(1))
    assert observe(s, ["A"], t(30)) == Repeated()
    assert observe(s, ["A"], t(61)) == Confirmed("A")
    assert s.last_confirmed("A") == t(61)


def test_quiet_boundary_exactly_quiet_ago_is_not_repeated():
    s = Sighting()
    observe(s, ["A"], t(0))
    observe(s, ["A"], t(0))
    assert observe(s, ["A"], t(59)) == Repeated()
    assert observe(s, ["A"], t(60)) == Confirmed("A")


def test_confirmed_again_after_quiet_even_with_a_new_streak():
    s = Sighting()
    observe(s, ["A"], t(0))
    observe(s, ["A"], t(1))
    observe(s, [], t(2))
    observe(s, ["A"], t(100))
    assert observe(s, ["A"], t(101)) == Confirmed("A")
    assert s.last_confirmed("A") == t(101)


def test_quiet_is_kept_per_identifier():
    s = Sighting()
    observe(s, ["A"], t(0))
    observe(s, ["A"], t(1))
    observe(s, ["B"], t(2))
    assert observe(s, ["B"], t(3)) == Confirmed("B")
    assert s.last_confirmed("A") == t(1)
    assert s.last_confirmed("B") == t(3)


def test_repeated_does_not_move_last_confirmed():
    s = Sighting()
    observe(s, ["A"], t(0))
    observe(s, ["A"], t(1))
    observe(s, ["A"], t(2))
    assert s.last_confirmed("A") == t(1)


def test_needed_is_an_argument():
    s = Sighting()
    assert observe(s, ["A"], t(0), needed=3) == Pending()
    assert observe(s, ["A"], t(1), needed=3) == Pending()
    assert observe(s, ["A"], t(2), needed=3) == Confirmed("A")


def test_needed_one_confirms_at_once():
    s = Sighting()
    assert observe(s, ["A"], t(0), needed=1) == Confirmed("A")


def test_needed_below_one_is_rejected():
    s = Sighting()
    with pytest.raises(ValueError):
        observe(s, ["A"], t(0), needed=0)


def test_last_confirmed_of_unknown_identifier_is_none():
    assert Sighting().last_confirmed("nope") is None
