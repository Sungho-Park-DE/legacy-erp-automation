from datetime import datetime, timedelta

from app import adapters
from app.adapters import flicker
from app.adapters.ports import PhoneEvent, ScreenReading
from app.modules.sighting_v1 import Ambiguous, Confirmed, Pending, Repeated
from app.syncs import (
    build_world,
    confirmed_sighting_joins_call,
    hang_up_ends_call,
    poll_phone,
    poll_screen,
    ring_starts_call,
    screen_reading_is_observed,
)

T0 = datetime(2026, 10, 24, 9, 0, 0)
NUMBER = "555-0142"
IDENTIFIER = "K7Q2M9X4"


def test_ring_starts_call():
    world = build_world()
    call = ring_starts_call(world, PhoneEvent("ring", NUMBER, T0))
    (view,) = world.calls.recent()
    assert (view.call, view.number, view.rang_at, view.ended_at) == (call, NUMBER, T0, None)


def test_hang_up_ends_the_open_call_from_that_number():
    world = build_world()
    other = ring_starts_call(world, PhoneEvent("ring", "555-0199", T0))
    mine = ring_starts_call(world, PhoneEvent("ring", NUMBER, T0 + timedelta(seconds=5)))
    ended = hang_up_ends_call(world, PhoneEvent("hang_up", NUMBER, T0 + timedelta(seconds=30)))
    by_call = {v.call: v for v in world.calls.recent()}
    assert ended == mine
    assert by_call[mine].ended_at == T0 + timedelta(seconds=30)
    assert by_call[other].ended_at is None


def test_hang_up_without_open_call_does_nothing():
    world = build_world()
    assert hang_up_ends_call(world, PhoneEvent("hang_up", NUMBER, T0)) is None
    ring_starts_call(world, PhoneEvent("ring", NUMBER, T0))
    hang_up_ends_call(world, PhoneEvent("hang_up", NUMBER, T0 + timedelta(seconds=30)))
    assert hang_up_ends_call(world, PhoneEvent("hang_up", NUMBER, T0 + timedelta(seconds=40))) is None
    assert world.log[-1].what == "no open call from this number"


def test_screen_reading_is_observed_by_sighting_with_the_settings():
    world = build_world()
    ring_starts_call(world, PhoneEvent("ring", NUMBER, T0))
    reading = ScreenReading(T0 + timedelta(seconds=2), [IDENTIFIER])
    assert isinstance(screen_reading_is_observed(world, reading), Pending)
    assert world.sighting.last_confirmed(IDENTIFIER) is None
    second = ScreenReading(T0 + timedelta(seconds=3), [IDENTIFIER])
    assert screen_reading_is_observed(world, second) == Confirmed(IDENTIFIER)
    assert world.sighting.last_confirmed(IDENTIFIER) == second.at


def test_ambiguous_reading_confirms_nothing_and_attaches_nothing():
    world = build_world()
    ring_starts_call(world, PhoneEvent("ring", NUMBER, T0))
    reading = ScreenReading(T0 + timedelta(seconds=2), [IDENTIFIER, "R3T8W5B1"])
    assert isinstance(screen_reading_is_observed(world, reading), Ambiguous)
    assert world.calls.recent()[0].items == ()


def test_confirmed_sighting_joins_the_call_in_the_window():
    world = build_world()
    call = ring_starts_call(world, PhoneEvent("ring", NUMBER, T0))
    joined = confirmed_sighting_joins_call(world, Confirmed(IDENTIFIER), T0 + timedelta(seconds=4))
    assert joined == call
    assert world.calls.recent()[0].items == (IDENTIFIER,)


def test_confirmed_sighting_outside_every_window_joins_nothing():
    world = build_world()
    ring_starts_call(world, PhoneEvent("ring", NUMBER, T0))
    assert confirmed_sighting_joins_call(world, Confirmed(IDENTIFIER), T0 - timedelta(minutes=5)) is None
    assert world.calls.recent()[0].items == ()


def test_confirmation_in_the_observe_sync_chains_into_the_call():
    world = build_world()
    ring_starts_call(world, PhoneEvent("ring", NUMBER, T0))
    for second in (2, 3):
        screen_reading_is_observed(world, ScreenReading(T0 + timedelta(seconds=second), [IDENTIFIER]))
    assert world.calls.recent()[0].items == (IDENTIFIER,)
    assert [e.sync for e in world.log][-2:] == ["ScreenReadingIsObserved", "ConfirmedSightingJoinsCall"]


def test_flicker_gives_pending_confirmed_repeated_and_one_attachment():
    phone = adapters.make_phone([PhoneEvent("ring", NUMBER, T0)])
    screen = adapters.make_screen(flicker(IDENTIFIER, T0 + timedelta(seconds=4), timedelta(seconds=1)))
    world = build_world(phone=phone, screen=screen)
    assert poll_phone(world) == 1
    results = poll_screen(world)
    assert [type(r) for r in results] == [Pending, Pending, Pending, Confirmed, Repeated]
    assert world.calls.recent()[0].items == (IDENTIFIER,)


def test_poll_phone_dispatches_ring_and_hang_up():
    events = [PhoneEvent("ring", NUMBER, T0), PhoneEvent("hang_up", NUMBER, T0 + timedelta(seconds=20))]
    world = build_world(phone=adapters.make_phone(events))
    assert poll_phone(world) == 2
    assert world.calls.recent()[0].ended_at == T0 + timedelta(seconds=20)
    assert poll_phone(world) == 0
