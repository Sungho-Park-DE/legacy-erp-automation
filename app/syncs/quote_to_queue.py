"""Syncs of docs/concepts/syncs.md, section "Quote to queue", plus one extra (OperatorAddsCatalogLine)."""
from __future__ import annotations

from collections.abc import Iterable
from decimal import Decimal

from app import flags
from app.modules.quote_v1 import LineNo, QuoteId

from .world import World


def operator_adds_catalog_line(
    world: World, quote: QuoteId, identifier: str, qty: int = 1, codes: Iterable[str] | None = None
) -> list[LineNo]:
    wanted = None if codes is None else set(codes)
    rows = [row for row in world.catalog.lookup(identifier) if wanted is None or row.code in wanted]
    lines = [world.quotes.add_line(quote, row.code, row.name, qty) for row in rows]
    world.emit("OperatorAddsCatalogLine", "lines added", quote=quote, identifier=identifier, lines=lines)
    return lines


def operator_sets_price(world: World, quote: QuoteId, line: LineNo, price: Decimal) -> None:
    world.quotes.set_price(quote, line, price)
    world.emit("OperatorSetsPrice", "price set", quote=quote, line=line, price=price)


def sent_quote_becomes_job(world: World, quote: QuoteId, request_save: bool) -> bool:
    lines = world.quotes.send(quote)
    payload = {
        "job": quote,
        "lines": [
            {"code": line.code, "name": line.name, "qty": line.qty, "price": line.price} for line in lines
        ],
        "save": request_save and flags.is_enabled("save"),
    }
    queued = world.queue.enqueue(quote, payload)
    world.emit(
        "SentQuoteBecomesJob",
        "job queued" if queued else "job id already known",
        job=quote,
        save_requested=request_save,
        save=payload["save"],
    )
    return queued
