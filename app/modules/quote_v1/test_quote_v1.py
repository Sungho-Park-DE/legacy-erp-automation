import inspect
from decimal import Decimal

import pytest

from app.modules.quote_v1 import (
    EmptyQuote,
    InvalidPrice,
    InvalidQuantity,
    Line,
    QuoteError,
    Quotes,
    QuoteSent,
    UnknownLine,
    UnknownQuote,
)


def test_operational_principle():
    quotes = Quotes()
    q = quotes.open()
    first = quotes.add_line(q, "A-1", "First item", 2)
    quotes.add_line(q, "B-2", "Second item", 1)
    quotes.set_price(q, first, Decimal("12.50"))

    lines = quotes.send(q)

    assert lines == [
        Line("A-1", "First item", 2, Decimal("12.50")),
        Line("B-2", "Second item", 1, None),
    ]
    with pytest.raises(QuoteSent):
        quotes.add_line(q, "C-3", "Third item", 1)
    with pytest.raises(QuoteSent):
        quotes.remove_line(q, first)
    with pytest.raises(QuoteSent):
        quotes.set_price(q, first, Decimal("1"))
    with pytest.raises(QuoteSent):
        quotes.send(q)
    assert quotes.view(q).lines == tuple(enumerate(lines, start=1))


def test_open_ids_are_deterministic_and_independent():
    quotes = Quotes()
    q1, q2 = quotes.open(), quotes.open()
    assert (q1, q2) == ("Q1", "Q2")
    quotes.add_line(q1, "A", "a", 1)
    assert quotes.view(q1).lines != ()
    assert quotes.view(q2).lines == ()
    assert Quotes().open() == "Q1"


def test_open_quote_is_not_sent_and_empty():
    quotes = Quotes()
    view = quotes.view(quotes.open())
    assert view.lines == ()
    assert view.sent is False


def test_add_line_effects_and_numbering():
    quotes = Quotes()
    q = quotes.open()
    a = quotes.add_line(q, "A", "a", 3)
    b = quotes.add_line(q, "B", "b", 1)
    assert (a, b) == (1, 2)
    assert quotes.view(q).lines == (
        (1, Line("A", "a", 3, None)),
        (2, Line("B", "b", 1, None)),
    )


@pytest.mark.parametrize("qty", [0, -1])
def test_add_line_requires_qty_at_least_one(qty):
    quotes = Quotes()
    q = quotes.open()
    with pytest.raises(InvalidQuantity):
        quotes.add_line(q, "A", "a", qty)
    assert quotes.view(q).lines == ()


@pytest.mark.parametrize("qty", [1.5, "2", True, None])
def test_add_line_requires_int_qty(qty):
    quotes = Quotes()
    q = quotes.open()
    with pytest.raises(InvalidQuantity):
        quotes.add_line(q, "A", "a", qty)


def test_add_line_has_no_price_parameter():
    params = inspect.signature(Quotes.add_line).parameters
    assert list(params) == ["self", "quote", "code", "name", "qty"]
    with pytest.raises(TypeError):
        Quotes().add_line("Q1", "A", "a", 1, price=Decimal("1"))


def test_set_price_is_the_only_price_path():
    quotes = Quotes()
    q = quotes.open()
    line = quotes.add_line(q, "A", "a", 1)
    quotes.set_price(q, line, Decimal("5"))
    assert quotes.view(q).lines[0][1].price == Decimal("5")
    quotes.set_price(q, line, Decimal("7.25"))
    assert quotes.view(q).lines[0][1].price == Decimal("7.25")


def test_set_price_accepts_zero():
    quotes = Quotes()
    q = quotes.open()
    line = quotes.add_line(q, "A", "a", 1)
    quotes.set_price(q, line, Decimal("0"))
    assert quotes.view(q).lines[0][1].price == Decimal("0")


@pytest.mark.parametrize("price", [Decimal("-0.01"), Decimal("NaN"), 5, 1.5, "3", None])
def test_set_price_requires_non_negative_decimal(price):
    quotes = Quotes()
    q = quotes.open()
    line = quotes.add_line(q, "A", "a", 1)
    with pytest.raises(InvalidPrice):
        quotes.set_price(q, line, price)
    assert quotes.view(q).lines[0][1].price is None


def test_set_price_only_touches_that_line():
    quotes = Quotes()
    q = quotes.open()
    a = quotes.add_line(q, "A", "a", 1)
    b = quotes.add_line(q, "B", "b", 1)
    quotes.set_price(q, b, Decimal("2"))
    lines = quotes.view(q).lines
    assert lines[0] == (a, Line("A", "a", 1, None))
    assert lines[1] == (b, Line("B", "b", 1, Decimal("2")))


def test_remove_line_keeps_numbers_of_other_lines_stable():
    quotes = Quotes()
    q = quotes.open()
    a = quotes.add_line(q, "A", "a", 1)
    b = quotes.add_line(q, "B", "b", 1)
    c = quotes.add_line(q, "C", "c", 1)
    quotes.remove_line(q, b)
    assert [no for no, _ in quotes.view(q).lines] == [a, c]
    quotes.set_price(q, c, Decimal("9"))
    assert quotes.send(q) == [
        Line("A", "a", 1, None),
        Line("C", "c", 1, Decimal("9")),
    ]


def test_removed_line_number_is_never_reused():
    quotes = Quotes()
    q = quotes.open()
    quotes.add_line(q, "A", "a", 1)
    b = quotes.add_line(q, "B", "b", 1)
    quotes.remove_line(q, b)
    d = quotes.add_line(q, "D", "d", 1)
    assert d == 3


def test_removed_line_is_unknown_afterwards():
    quotes = Quotes()
    q = quotes.open()
    a = quotes.add_line(q, "A", "a", 1)
    quotes.remove_line(q, a)
    with pytest.raises(UnknownLine):
        quotes.remove_line(q, a)
    with pytest.raises(UnknownLine):
        quotes.set_price(q, a, Decimal("1"))


def test_unknown_line_and_quote():
    quotes = Quotes()
    q = quotes.open()
    with pytest.raises(UnknownLine):
        quotes.set_price(q, 99, Decimal("1"))
    with pytest.raises(UnknownLine):
        quotes.remove_line(q, 99)
    for call in (
        lambda: quotes.add_line("nope", "A", "a", 1),
        lambda: quotes.remove_line("nope", 1),
        lambda: quotes.set_price("nope", 1, Decimal("1")),
        lambda: quotes.send("nope"),
        lambda: quotes.view("nope"),
    ):
        with pytest.raises(UnknownQuote):
            call()


def test_send_requires_at_least_one_line():
    quotes = Quotes()
    q = quotes.open()
    with pytest.raises(EmptyQuote):
        quotes.send(q)
    a = quotes.add_line(q, "A", "a", 1)
    quotes.remove_line(q, a)
    with pytest.raises(EmptyQuote):
        quotes.send(q)
    assert quotes.view(q).sent is False


def test_send_effects_marks_sent():
    quotes = Quotes()
    q = quotes.open()
    quotes.add_line(q, "A", "a", 1)
    assert quotes.view(q).sent is False
    quotes.send(q)
    assert quotes.view(q).sent is True


def test_lines_are_immutable_and_results_are_copies():
    quotes = Quotes()
    q = quotes.open()
    quotes.add_line(q, "A", "a", 1)
    sent = quotes.send(q)
    with pytest.raises(AttributeError):
        sent[0].qty = 5
    sent.clear()
    assert len(quotes.view(q).lines) == 1


def test_errors_are_value_errors():
    for exc in (QuoteSent, InvalidQuantity, InvalidPrice, EmptyQuote, UnknownLine, UnknownQuote):
        assert issubclass(exc, QuoteError)
        assert issubclass(exc, ValueError)
