"""Glue that feeds adapter output into the syncs. Not syncs themselves: no concept is touched here."""
from __future__ import annotations

from app.modules.sighting_v1 import Result

from .calls_and_screen import hang_up_ends_call, ring_starts_call, screen_reading_is_observed
from .world import World


def poll_phone(world: World) -> int:
    events = world.phone.poll()
    for event in events:
        if event.kind == "ring":
            ring_starts_call(world, event)
        elif event.kind == "hang_up":
            hang_up_ends_call(world, event)
    return len(events)


def poll_screen(world: World) -> list[Result]:
    results = []
    while (reading := world.screen.read()) is not None:
        results.append(screen_reading_is_observed(world, reading))
    return results
