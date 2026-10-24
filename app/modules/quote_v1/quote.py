from dataclasses import dataclass, replace
from decimal import Decimal

QuoteId = str
LineNo = int


class QuoteError(ValueError):
    pass


class UnknownQuote(QuoteError):
    pass


class UnknownLine(QuoteError):
    pass


class QuoteSent(QuoteError):
    pass


class InvalidQuantity(QuoteError):
    pass


class InvalidPrice(QuoteError):
    pass


class EmptyQuote(QuoteError):
    pass


@dataclass(frozen=True)
class Line:
    code: str
    name: str
    qty: int
    price: Decimal | None = None


@dataclass(frozen=True)
class QuoteView:
    lines: tuple[tuple[LineNo, Line], ...]
    sent: bool


class _Quote:
    def __init__(self) -> None:
        self.lines: dict[LineNo, Line] = {}
        self.next_no = 1
        self.sent = False


class Quotes:
    """Line numbers are 1-based, assigned in order and never reused: removing a line leaves the others' numbers unchanged."""

    def __init__(self) -> None:
        self._quotes: dict[QuoteId, _Quote] = {}

    def open(self) -> QuoteId:
        quote_id = f"Q{len(self._quotes) + 1}"
        self._quotes[quote_id] = _Quote()
        return quote_id

    def add_line(self, quote: QuoteId, code: str, name: str, qty: int) -> LineNo:
        q = self._open_quote(quote)
        if type(qty) is not int or qty < 1:
            raise InvalidQuantity(f"qty must be an int >= 1, got {qty!r}")
        no = q.next_no
        q.next_no += 1
        q.lines[no] = Line(code, name, qty, None)
        return no

    def remove_line(self, quote: QuoteId, line: LineNo) -> None:
        q = self._open_quote(quote)
        self._line(q, line)
        del q.lines[line]

    def set_price(self, quote: QuoteId, line: LineNo, price: Decimal) -> None:
        q = self._open_quote(quote)
        if not isinstance(price, Decimal) or not price.is_finite() or price < 0:
            raise InvalidPrice(f"price must be a finite Decimal >= 0, got {price!r}")
        q.lines[line] = replace(self._line(q, line), price=price)

    def send(self, quote: QuoteId) -> list[Line]:
        q = self._open_quote(quote)
        if not q.lines:
            raise EmptyQuote(f"quote {quote} has no lines")
        q.sent = True
        return list(q.lines.values())

    def view(self, quote: QuoteId) -> QuoteView:
        q = self._get(quote)
        return QuoteView(lines=tuple(q.lines.items()), sent=q.sent)

    def _get(self, quote: QuoteId) -> _Quote:
        try:
            return self._quotes[quote]
        except (KeyError, TypeError):
            raise UnknownQuote(f"unknown quote {quote!r}") from None

    def _open_quote(self, quote: QuoteId) -> _Quote:
        q = self._get(quote)
        if q.sent:
            raise QuoteSent(f"quote {quote} was already sent")
        return q

    @staticmethod
    def _line(q: _Quote, line: LineNo) -> Line:
        try:
            return q.lines[line]
        except (KeyError, TypeError):
            raise UnknownLine(f"unknown line {line!r}") from None
