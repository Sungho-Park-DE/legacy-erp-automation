from decimal import Decimal

import pytest

from app.modules.jobqueue_v1 import JobState
from app.modules.quote_v1 import QuoteSent
from app.syncs import build_world, operator_adds_catalog_line, operator_sets_price, sent_quote_becomes_job

IDENTIFIER = "K7Q2M9X4"


@pytest.fixture(autouse=True)
def save_flag_off(monkeypatch):
    monkeypatch.delenv("LEA_FLAG_SAVE", raising=False)


def quote_with_two_lines(world):
    quote = world.quotes.open()
    first, second = operator_adds_catalog_line(world, quote, IDENTIFIER, qty=2)
    return quote, first, second


def test_operator_adds_catalog_line_turns_catalog_rows_into_lines():
    world = build_world()
    quote = world.quotes.open()
    assert operator_adds_catalog_line(world, quote, IDENTIFIER, qty=2) == [1, 2]
    lines = [line for _, line in world.quotes.view(quote).lines]
    assert [(line.code, line.name, line.qty, line.price) for line in lines] == [
        ("P-100", "Widget small", 2, None),
        ("P-101", "Widget large", 2, None),
    ]


def test_operator_adds_only_the_chosen_codes_and_nothing_for_unknown_identifiers():
    world = build_world()
    quote = world.quotes.open()
    assert operator_adds_catalog_line(world, quote, IDENTIFIER, codes=["P-101"]) == [1]
    assert operator_adds_catalog_line(world, quote, "UNKNOWN0") == []
    assert [line.code for _, line in world.quotes.view(quote).lines] == ["P-101"]


def test_operator_sets_price_goes_to_the_quote():
    world = build_world()
    quote, first, _ = quote_with_two_lines(world)
    operator_sets_price(world, quote, first, Decimal("12.50"))
    prices = {no: line.price for no, line in world.quotes.view(quote).lines}
    assert prices == {1: Decimal("12.50"), 2: None}


def test_sent_quote_becomes_a_queued_job_with_the_payload_shape():
    world = build_world()
    quote, first, _ = quote_with_two_lines(world)
    operator_sets_price(world, quote, first, Decimal("12.50"))
    assert sent_quote_becomes_job(world, quote, request_save=False) is True
    assert world.queue.status(quote).state is JobState.QUEUED
    job, payload = world.queue.take()
    assert job == quote
    assert payload == {
        "job": quote,
        "lines": [
            {"code": "P-100", "name": "Widget small", "qty": 2, "price": Decimal("12.50")},
            {"code": "P-101", "name": "Widget large", "qty": 2, "price": None},
        ],
        "save": False,
    }
    assert world.quotes.view(quote).sent is True


def test_save_is_requested_but_flag_off_means_dry_run(monkeypatch):
    world = build_world()
    quote, _, _ = quote_with_two_lines(world)
    sent_quote_becomes_job(world, quote, request_save=True)
    assert world.queue.take()[1]["save"] is False


def test_save_is_kept_only_when_requested_and_flag_on(monkeypatch):
    monkeypatch.setenv("LEA_FLAG_SAVE", "1")
    world = build_world()
    asked, _, _ = quote_with_two_lines(world)
    not_asked, _, _ = quote_with_two_lines(world)
    sent_quote_becomes_job(world, asked, request_save=True)
    sent_quote_becomes_job(world, not_asked, request_save=False)
    assert world.queue.take()[1]["save"] is True
    world.queue.finish(asked, JobState.DONE)
    assert world.queue.take()[1]["save"] is False


def test_sending_the_same_quote_twice_gives_one_job():
    world = build_world()
    quote, _, _ = quote_with_two_lines(world)
    sent_quote_becomes_job(world, quote, request_save=False)
    with pytest.raises(QuoteSent):
        sent_quote_becomes_job(world, quote, request_save=False)
    assert world.queue.list() == [quote]


def test_queue_itself_refuses_a_known_job_id():
    world = build_world()
    quote, _, _ = quote_with_two_lines(world)
    sent_quote_becomes_job(world, quote, request_save=False)
    assert world.queue.enqueue(quote, {"job": quote, "lines": [], "save": False}) is False
    assert world.queue.list() == [quote]
