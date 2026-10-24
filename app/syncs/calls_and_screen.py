"""Syncs of docs/concepts/syncs.md, section "Calls and screen"."""
from __future__ import annotations

from app import settings
from app.adapters.ports import PhoneEvent, ScreenReading
from app.modules.call_v1 import CallId
from app.modules.sighting_v1 import Confirmed, Result

from .world import World


def ring_starts_call(world: World, event: PhoneEvent) -> CallId:
    call = world.calls.ring(event.number, event.at)
    world.emit("RingStartsCall", "call started", call=call, number=event.number)
    return call


def hang_up_ends_call(world: World, event: PhoneEvent) -> CallId | None:
    open_call = next((c for c in world.calls.recent() if c.number == event.number and c.ended_at is None), None)
    if open_call is None:
        world.emit("HangUpEndsCall", "no open call from this number", number=event.number)
        return None
    world.calls.hang_up(open_call.call, event.at)
    world.emit("HangUpEndsCall", "call ended", call=open_call.call, number=event.number)
    return open_call.call


def screen_reading_is_observed(world: World, reading: ScreenReading) -> Result:
    result = world.sighting.observe(
        reading.candidates, reading.selected, reading.at, settings.SIGHTING_NEEDED, settings.SIGHTING_QUIET
    )
    world.emit(
        "ScreenReadingIsObserved",
        type(result).__name__,
        candidates=list(reading.candidates),
        selected=reading.selected,
        at=reading.at,
    )
    if isinstance(result, Confirmed):
        confirmed_sighting_joins_call(world, result, reading.at)
    return result


def confirmed_sighting_joins_call(world: World, confirmed: Confirmed, at) -> CallId | None:
    call = world.calls.attach(confirmed.id, at, settings.CALL_BEFORE, settings.CALL_AFTER)
    world.emit("ConfirmedSightingJoinsCall", "attached" if call is not None else "no call in window", id=confirmed.id, call=call)
    return call
