"""The one place where a real or a fake outside system is chosen (settings LEA_ERP, LEA_CATALOG, LEA_PHONE, LEA_SCREEN).

This repository ships fakes only; a real adapter is a new module here, chosen by the same setting.
"""
from __future__ import annotations

from collections.abc import Iterable

from app import settings
from app.adapters.fake_catalog import FakeCatalog
from app.adapters.fake_erp import FakeErpViewer, SimulatedCrash, ViewerError
from app.adapters.fake_phone import ScriptedPhone
from app.adapters.fake_screen import ScriptedScreen, flicker
from app.adapters.ports import Catalog, ErpRecipe, ErpViewer, PhoneEvent, PhoneLog, ScreenReading, ScreenText
from app.adapters.recipe import FakeRecipe

__all__ = [
    "FakeCatalog",
    "FakeErpViewer",
    "FakeRecipe",
    "ScriptedPhone",
    "ScriptedScreen",
    "SimulatedCrash",
    "ViewerError",
    "flicker",
    "make_catalog",
    "make_erp",
    "make_phone",
    "make_recipe",
    "make_screen",
]


def _only_fake(name: str, value: str) -> None:
    if value != "fake":
        raise ValueError(
            f"{name}={value!r} is not available: only 'fake' exists. "
            f"A real adapter is a new module in app/adapters, chosen here."
        )


def make_erp() -> ErpViewer:
    _only_fake("LEA_ERP", settings.ERP)
    return FakeErpViewer()


def make_recipe() -> ErpRecipe:
    _only_fake("LEA_ERP", settings.ERP)
    return FakeRecipe()


def make_catalog() -> Catalog:
    _only_fake("LEA_CATALOG", settings.CATALOG)
    return FakeCatalog()


def make_phone(events: Iterable[PhoneEvent] = ()) -> PhoneLog:
    _only_fake("LEA_PHONE", settings.PHONE)
    return ScriptedPhone(events)


def make_screen(readings: Iterable[ScreenReading] = ()) -> ScreenText:
    _only_fake("LEA_SCREEN", settings.SCREEN)
    return ScriptedScreen(readings)
