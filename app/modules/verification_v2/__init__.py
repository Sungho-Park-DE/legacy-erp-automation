from collections import Counter
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation

__all__ = ["Verification", "Match", "Mismatch", "Found", "NotFound", "Many"]


@dataclass(frozen=True)
class Match:
    pass


@dataclass(frozen=True)
class Mismatch:
    reasons: tuple


@dataclass(frozen=True)
class Found:
    ref: str


@dataclass(frozen=True)
class NotFound:
    pass


@dataclass(frozen=True)
class Many:
    refs: tuple


def _number(value):
    try:
        number = Decimal(str(value).strip())
    except InvalidOperation:
        return None
    return number if number.is_finite() else None


def _show(value, number):
    if number is None:
        return repr(value) if isinstance(value, str) else str(value)
    return format(number.normalize(), "f")


def _key(line):
    qty = line.get("qty")
    number = _number(qty)
    return (line["code"], number if number is not None else qty)


def _show_key(key):
    code, qty = key
    return f"{code} x{_show(qty, qty if isinstance(qty, Decimal) else None)}"


class Verification:
    def __init__(self):
        self._results = {}

    def compare(self, job, expected, actual):
        outcome = self._compare(expected, actual)
        self._results[job] = outcome
        return outcome

    def _compare(self, expected, actual):
        actual_header = actual.get("header", {})
        actual_lines = actual.get("lines", [])
        own_ref = actual_header.get("ref")
        for line in actual_lines:
            if "ref" in line and line["ref"] != own_ref:
                return Mismatch((f"line from another document {line['ref']}",))

        reasons = []
        for key, wanted in expected.get("header", {}).items():
            found = actual_header.get(key)
            if found != wanted:
                reasons.append(f"header {key}: {wanted!r} != {found!r}")

        expected_lines = expected.get("lines", [])
        want = Counter(_key(line) for line in expected_lines)
        have = Counter(_key(line) for line in actual_lines)
        for key in want:
            for _ in range(want[key] - have.get(key, 0)):
                reasons.append(f"missing {_show_key(key)}")
        for key in have:
            for _ in range(have[key] - want.get(key, 0)):
                reasons.append(f"extra {_show_key(key)}")

        for line in expected_lines:
            price = line.get("price")
            if price is None:
                continue
            key = _key(line)
            candidates = [a for a in actual_lines if _key(a) == key]
            if not candidates:
                continue
            wanted = _number(price)
            prices = [a.get("price") for a in candidates]
            if wanted is not None and any(_number(p) == wanted for p in prices):
                continue
            got = prices[0]
            reasons.append(
                f"price {line['code']}: {_show(price, wanted)} != {_show(got, _number(got))}"
            )

        return Mismatch(tuple(reasons)) if reasons else Match()

    def result(self, job):
        return self._results.get(job)

    def locate(self, job, documents, known_before):
        refs = sorted(
            {
                d["ref"]
                for d in documents
                if d.get("note") == job and d["ref"] not in known_before
            }
        )
        if not refs:
            return NotFound()
        if len(refs) == 1:
            return Found(refs[0])
        return Many(tuple(refs))
