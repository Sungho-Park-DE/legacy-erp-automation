# Concept: Quote [Item]

**Purpose:** Let the operator build a quote line by line and send it on, where only a person ever sets a price.

**Operational principle:** If the operator adds two lines and sets a price on one, then sending the quote returns both lines, one with the operator's price and one with no price (the target system's own price applies); after sending, the quote can no longer be changed.

**State:**
- quotes: QuoteId -> { lines: list Line, sent: bool }
- Line = { code: str, name: str, qty: int, price: decimal? }

**Actions:**
- open() -> QuoteId
- add_line(quote, code, name, qty) -> LineNo
  - requires: not sent, qty >= 1
- remove_line(quote, line)
  - requires: not sent
- set_price(quote, line, price)
  - requires: not sent, price >= 0
  - effects: the line's price; there is no other way to set a price, and only operator requests call this (sync `OperatorSetsPrice`)
- send(quote) -> list Line
  - requires: not sent, at least one line
  - effects: sent = true

**Queries:**
- view(quote) -> { lines, sent }

**Not this concept's job:** where codes come from (catalog adapter), what happens after sending (JobQueue, via a sync), how lines are typed into the target system (ERP recipe).
