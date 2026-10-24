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
    def list_documents(self) -> list[Document]:
        """Every document the list screen shows, header only (`ref`, `note`?, `status`?), lines empty."""
        ...

    def request_log(self) -> list[str]:
        """The viewer's own log of requests it sent to the ERP server, oldest first, one name per request."""
        ...

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
    """How one job is typed into the ERP: screens, field paths, functions.

    A recipe that can remove a line also names, as attributes, the function that removes it (`removal_fn`) and the
    field that holds the code of the item being removed (`item_field`), so that the syncs know neither.
    """

    removal_fn: str
    item_field: str

    def steps(self, payload: dict) -> list[Step]: ...
    def read_back_steps(self, job: str) -> list[Step]:
        """Steps (checked by ActionPolicy like any other) that bring the viewer to where `read_back` works."""
        ...

    def read_back_ref(self, job: str) -> str: ...
    def edit_steps(self, ref: str, ops: list[dict]) -> list[Step]:
        """Steps that load document `ref` and apply Revision ops ({op: remove|qty|add, code, qty?, price?}), ending in a save step."""
        ...

    def item_in_dialog(self, text: str) -> str | None:
        """The item code a confirmation dialog names, or None if it names none."""
        ...


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
