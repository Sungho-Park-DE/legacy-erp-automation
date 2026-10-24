"""Contracts for the outside systems. Concepts never see these; only app/syncs does."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Protocol


class ErpViewer(Protocol):
    """Scripting interface of a legacy ActiveX form viewer (modelled, not copied, from a real one)."""

    def open_screen(self, screen: str) -> None: ...
    def set_value(self, path: str, value: str) -> None: ...
    def call(self, fn: str) -> None: ...
    def pending_dialog(self) -> str | None: ...
    def answer_dialog(self, accept: bool) -> None: ...
    def read_back(self, ref: str) -> Document: ...
    def reset(self) -> None: ...


@dataclass(frozen=True)
class Document:
    header: dict[str, str]
    lines: list[dict] = field(default_factory=list)  # {code, qty, price?}


@dataclass(frozen=True)
class Open:
    screen: str


@dataclass(frozen=True)
class Set:
    path: str
    value: str


@dataclass(frozen=True)
class Call:
    fn: str
    is_save: bool = False


Step = Open | Set | Call


class ErpRecipe(Protocol):
    """How one job is typed into the ERP: screens, field paths, functions."""

    def steps(self, payload: dict) -> list[Step]: ...
    def read_back_ref(self, job: str) -> str: ...


@dataclass(frozen=True)
class CatalogRow:
    code: str
    name: str


class Catalog(Protocol):
    def lookup(self, identifier: str) -> list[CatalogRow]: ...


@dataclass(frozen=True)
class PhoneEvent:
    kind: str  # "ring" | "hang_up"
    number: str
    at: datetime


class PhoneLog(Protocol):
    def poll(self) -> list[PhoneEvent]: ...


@dataclass(frozen=True)
class ScreenReading:
    at: datetime
    candidates: list[str]
    selected: str | None = None


class ScreenText(Protocol):
    def read(self) -> ScreenReading | None: ...
