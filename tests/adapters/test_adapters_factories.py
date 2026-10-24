from datetime import datetime

import pytest

from app import adapters, settings
from app.adapters import FakeCatalog, FakeErpViewer, FakeRecipe, ScriptedPhone, ScriptedScreen
from app.adapters.ports import PhoneEvent, ScreenReading


def test_defaults_give_fakes():
    assert isinstance(adapters.make_erp(), FakeErpViewer)
    assert isinstance(adapters.make_recipe(), FakeRecipe)
    assert isinstance(adapters.make_catalog(), FakeCatalog)
    assert isinstance(adapters.make_phone(), ScriptedPhone)
    assert isinstance(adapters.make_screen(), ScriptedScreen)


def test_factories_return_fresh_instances():
    assert adapters.make_erp() is not adapters.make_erp()
    assert adapters.make_catalog() is not adapters.make_catalog()


def test_phone_and_screen_take_scripts():
    at = datetime(2026, 1, 5, 9, 0, 0)
    events = [PhoneEvent("ring", "0100", at)]
    readings = [ScreenReading(at, ["A"])]
    assert adapters.make_phone(events).poll() == events
    assert adapters.make_screen(readings).read() == readings[0]
    assert adapters.make_phone().poll() == []
    assert adapters.make_screen().read() is None


def test_explicit_fake_setting_works(monkeypatch):
    monkeypatch.setattr(settings, "ERP", "fake")
    assert isinstance(adapters.make_erp(), FakeErpViewer)


@pytest.mark.parametrize(
    "setting, factory",
    [
        ("ERP", adapters.make_erp),
        ("ERP", adapters.make_recipe),
        ("CATALOG", adapters.make_catalog),
        ("PHONE", adapters.make_phone),
        ("SCREEN", adapters.make_screen),
    ],
)
def test_non_fake_setting_raises_clear_error(monkeypatch, setting, factory):
    monkeypatch.setattr(settings, setting, "real")
    with pytest.raises(ValueError) as error:
        factory()
    message = str(error.value)
    assert f"LEA_{setting}" in message
    assert "'real'" in message
    assert "new module" in message


def test_exports():
    for name in ("FakeErpViewer", "FakeRecipe", "FakeCatalog", "ScriptedPhone", "ScriptedScreen", "ViewerError", "flicker"):
        assert hasattr(adapters, name)
