from datetime import datetime, timedelta

from app.adapters import FakeCatalog, ScriptedPhone, ScriptedScreen, flicker
from app.adapters.fake_catalog import DEFAULT_ROWS
from app.adapters.ports import Catalog, CatalogRow, PhoneEvent, PhoneLog, ScreenReading, ScreenText

T0 = datetime(2026, 1, 5, 9, 0, 0)
STEP = timedelta(seconds=1)


def test_satisfy_ports():
    catalog: Catalog = FakeCatalog()
    phone: PhoneLog = ScriptedPhone([])
    screen: ScreenText = ScriptedScreen([])
    assert callable(catalog.lookup) and callable(phone.poll) and callable(screen.read)


def test_catalog_default_rows_and_unknown():
    catalog = FakeCatalog()
    identifier = next(iter(DEFAULT_ROWS))
    assert len(identifier) == 8
    assert catalog.lookup(identifier) == DEFAULT_ROWS[identifier]
    assert CatalogRow("P-100", "Widget small") in catalog.lookup("K7Q2M9X4")
    assert catalog.lookup("ZZZZZZZZ") == []


def test_catalog_custom_rows_and_isolation():
    catalog = FakeCatalog({"AAAA1111": [CatalogRow("X-1", "Thing")]})
    assert catalog.lookup("AAAA1111") == [CatalogRow("X-1", "Thing")]
    assert catalog.lookup("K7Q2M9X4") == []
    catalog.lookup("AAAA1111").clear()
    assert len(catalog.lookup("AAAA1111")) == 1
    assert FakeCatalog({}).lookup("AAAA1111") == []


def test_phone_returns_each_event_once():
    events = [PhoneEvent("ring", "0100", T0), PhoneEvent("hang_up", "0100", T0 + STEP)]
    phone = ScriptedPhone(events)
    assert phone.poll() == events
    assert phone.poll() == []
    assert phone.poll() == []


def test_phone_empty():
    assert ScriptedPhone([]).poll() == []


def test_screen_plays_script_then_none():
    readings = [ScreenReading(T0, ["A"]), ScreenReading(T0 + STEP, ["A"], selected="A")]
    screen = ScriptedScreen(readings)
    assert screen.read() == readings[0]
    assert screen.read() == readings[1]
    assert screen.read() is None
    assert screen.read() is None


def test_flicker_sequence():
    readings = flicker("K7Q2M9X4", T0, STEP)
    assert [r.candidates for r in readings] == [[], ["K7Q2"], ["K7Q2M9X4"], ["K7Q2M9X4"], ["K7Q2M9X4"]]
    assert [r.at for r in readings] == [T0 + STEP * i for i in range(5)]
    assert all(r.selected is None for r in readings)


def test_flicker_options():
    readings = flicker("K7Q2M9X4", T0, STEP, partial=("", "K7#"), settle_readings=2)
    assert [r.candidates for r in readings] == [[], [""], ["K7#"], ["K7Q2M9X4"], ["K7Q2M9X4"]]


def test_flicker_with_noise_is_ambiguous():
    readings = flicker("K7Q2M9X4", T0, STEP, settle_readings=2, noise="R3T8W5B1")
    assert [r.candidates for r in readings][-2:] == [["K7Q2M9X4", "R3T8W5B1"]] * 2
    assert all(r.selected is None for r in readings)


def test_flicker_readings_are_independent_objects():
    readings = flicker("K7Q2M9X4", T0, STEP)
    readings[-1].candidates.append("x")
    assert readings[-2].candidates == ["K7Q2M9X4"]


def test_flicker_feeds_scripted_screen():
    screen = ScriptedScreen(flicker("K7Q2M9X4", T0, STEP, settle_readings=1))
    seen = []
    while (reading := screen.read()) is not None:
        seen.append(reading)
    assert len(seen) == 3
