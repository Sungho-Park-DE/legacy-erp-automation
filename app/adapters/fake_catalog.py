"""Invented catalog: opaque 8-character identifiers mapped to rows."""
from __future__ import annotations

from app.adapters.ports import CatalogRow

DEFAULT_ROWS: dict[str, list[CatalogRow]] = {
    "K7Q2M9X4": [CatalogRow("P-100", "Widget small"), CatalogRow("P-101", "Widget large")],
    "R3T8W5B1": [CatalogRow("P-200", "Gizmo set")],
    "D6N4C2Z7": [CatalogRow("P-300", "Gadget"), CatalogRow("P-301", "Gadget long"), CatalogRow("P-302", "Gizmo pack")],
}


class FakeCatalog:
    def __init__(self, rows_by_identifier: dict[str, list[CatalogRow]] | None = None):
        source = DEFAULT_ROWS if rows_by_identifier is None else rows_by_identifier
        self._rows = {identifier: list(rows) for identifier, rows in source.items()}

    def lookup(self, identifier: str) -> list[CatalogRow]:
        return list(self._rows.get(identifier, []))
