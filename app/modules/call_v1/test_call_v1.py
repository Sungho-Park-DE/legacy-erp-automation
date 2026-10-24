from datetime import datetime, timedelta

import pytest

from app.modules.call_v1 import (
    CallAlreadyEnded,
    CallView,
    Calls,
    UnknownCall,
)

BEFORE = timedelta(seconds=10)
AFTER = timedelta(minutes=10)
D = datetime(2026, 1, 5)


def at(h: int, m: int = 0, s: int = 0) -> datetime:
    return D.replace(hour=h, minute=m, second=s)


def attach(c: Calls, item, when, before=BEFORE, after=AFTER):
    return c.attach(item, when, before, after)


def test_operational_principle():
    c = Calls()
    call = c.ring("555-0100", at(10, 0, 0))
    c.hang_up(call, at(10, 3, 0))

    assert attach(c, "inside", at(10, 2, 0)) == call
    assert attach(c, "just-before", at(9, 59, 55)) == call
    assert attach(c, "much-later", at(10, 30, 0)) is None

    [view] = c.recent(10)
    assert view == CallView(
        call=call,
        number="555-0100",
        rang_at=at(10, 0, 0),
        ended_at=at(10, 3, 0),
        items=("inside", "just-before"),
    )


def test_ring_creates_a_new_call_without_items():
    c = Calls()
    a = c.ring("1", at(10))
    b = c.ring("2", at(11))
    assert a != b
    views = {v.call: v for v in c.recent(10)}
    assert views[a].number == "1"
    assert views[a].rang_at == at(10)
    assert views[a].ended_at is None
    assert views[a].items == ()
    assert views[b].items == ()


def test_hang_up_sets_ended_at():
    c = Calls()
    call = c.ring("1", at(10))
    c.hang_up(call, at(10, 5))
    assert c.recent(1)[0].ended_at == at(10, 5)


def test_hang_up_unknown_call_is_rejected():
    c = Calls()
    with pytest.raises(UnknownCall):
        c.hang_up(99, at(10))
    assert issubclass(UnknownCall, ValueError)


def test_hang_up_twice_is_rejected_and_keeps_the_first_end():
    c = Calls()
    call = c.ring("1", at(10))
    c.hang_up(call, at(10, 5))
    with pytest.raises(CallAlreadyEnded):
        c.hang_up(call, at(10, 6))
    assert issubclass(CallAlreadyEnded, ValueError)
    assert c.recent(1)[0].ended_at == at(10, 5)


def test_attach_without_any_call_returns_none():
    assert attach(Calls(), "x", at(10)) is None


def test_attach_window_edges_are_inclusive_for_an_ended_call():
    c = Calls()
    call = c.ring("1", at(10, 0, 0))
    c.hang_up(call, at(10, 3, 0))
    assert attach(c, "a", at(9, 59, 50)) == call
    assert attach(c, "b", at(9, 59, 49)) is None
    assert attach(c, "c", at(10, 13, 0)) == call
    assert attach(c, "d", at(10, 13, 1)) is None
    assert c.recent(1)[0].items == ("a", "c")


def test_attach_to_an_open_call_has_no_upper_limit():
    c = Calls()
    call = c.ring("1", at(10))
    assert attach(c, "x", at(23, 59)) == call


def test_attach_before_an_open_call_respects_the_lower_limit():
    c = Calls()
    c.ring("1", at(10))
    assert attach(c, "x", at(9, 59, 49)) is None
    assert attach(c, "y", at(9, 59, 50)) is not None


def test_windows_are_arguments():
    c = Calls()
    call = c.ring("1", at(10))
    c.hang_up(call, at(10, 1))
    assert attach(c, "x", at(10, 1, 30), after=timedelta(seconds=30)) == call
    assert attach(c, "y", at(10, 1, 31), after=timedelta(seconds=30)) is None
    assert attach(c, "z", at(9, 59), before=timedelta(minutes=1)) == call


def test_attach_picks_the_most_recent_matching_call():
    c = Calls()
    old = c.ring("1", at(10, 0))
    c.hang_up(old, at(10, 2))
    new = c.ring("2", at(10, 4))
    c.hang_up(new, at(10, 6))
    assert attach(c, "x", at(10, 5)) == new
    assert attach(c, "y", at(10, 1)) == old
    assert attach(c, "z", at(10, 3)) == old
    views = {v.call: v for v in c.recent(10)}
    assert views[new].items == ("x",)
    assert views[old].items == ("y", "z")


def test_attach_prefers_the_latest_ring_even_if_an_older_call_is_still_open():
    c = Calls()
    c.ring("1", at(10, 0))
    new = c.ring("2", at(10, 1))
    assert attach(c, "x", at(10, 2)) == new


def test_attach_skips_a_more_recent_call_that_does_not_match():
    c = Calls()
    old = c.ring("1", at(10, 0))
    c.hang_up(old, at(10, 20))
    c.ring("2", at(10, 30))
    assert attach(c, "x", at(10, 25)) == old


def test_same_item_is_not_added_twice_to_a_call():
    c = Calls()
    call = c.ring("1", at(10))
    assert attach(c, "x", at(10, 1)) == call
    assert attach(c, "x", at(10, 2)) == call
    assert attach(c, "y", at(10, 3)) == call
    assert c.recent(1)[0].items == ("x", "y")


def test_unmatched_attach_changes_nothing():
    c = Calls()
    call = c.ring("1", at(10))
    c.hang_up(call, at(10, 1))
    before = c.recent(10)
    assert attach(c, "x", at(12)) is None
    assert c.recent(10) == before


def test_recent_is_most_recent_first_and_limited():
    c = Calls()
    first = c.ring("1", at(10))
    second = c.ring("2", at(11))
    third = c.ring("3", at(12))
    assert [v.call for v in c.recent(10)] == [third, second, first]
    assert [v.call for v in c.recent(2)] == [third, second]
    assert c.recent(0) == []


def test_recent_orders_by_ring_time_not_by_creation():
    c = Calls()
    late = c.ring("1", at(12))
    early = c.ring("2", at(10))
    assert [v.call for v in c.recent(10)] == [late, early]


def test_recent_without_limit_returns_all():
    c = Calls()
    for i in range(5):
        c.ring(str(i), at(10, i))
    assert len(c.recent()) == 5


def test_recent_negative_limit_is_rejected():
    with pytest.raises(ValueError):
        Calls().recent(-1)


def test_recent_views_are_snapshots():
    c = Calls()
    call = c.ring("1", at(10))
    [snapshot] = c.recent(1)
    attach(c, "x", at(10, 1))
    c.hang_up(call, at(10, 2))
    assert snapshot.items == ()
    assert snapshot.ended_at is None
