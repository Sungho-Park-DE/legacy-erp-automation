# quote_v1

Concept `Quote` (`docs/concepts/Quote.md`). Import only from `app.modules.quote_v1`; state is in memory inside one `Quotes()` instance.

- `Quotes.open() -> QuoteId` (`"Q1"`, `"Q2"`, ...)
- `add_line(quote, code, name, qty) -> LineNo` (no price argument; `qty` int >= 1)
- `set_price(quote, line, price: Decimal)` (the only way to set a price; `price >= 0`)
- `remove_line(quote, line)` (line numbers are 1-based and never reused or shifted)
- `send(quote) -> list[Line]`, `Line(code, name, qty, price: Decimal | None)` is frozen; marks the quote sent
- `view(quote) -> QuoteView(lines: tuple[(LineNo, Line), ...], sent: bool)`
- Errors, all `ValueError`s (base `QuoteError`): `UnknownQuote`, `UnknownLine`, `QuoteSent`, `InvalidQuantity`, `InvalidPrice`, `EmptyQuote`
