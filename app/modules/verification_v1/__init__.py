from dataclasses import dataclass
from decimal import Decimal, InvalidOperation

__all__ = ["Verification", "Match", "Mismatch"]


@dataclass(frozen=True)
class Match:
    pass


@dataclass(frozen=True)
class Mismatch:
    reasons: tuple


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


def _differ(code, label, expected, actual):
    left, right = _number(expected), _number(actual)
    if left is not None and right is not None and left == right:
        return None
    return f"{label} {code}: {_show(expected, left)} != {_show(actual, right)}"


def _by_code(lines):
    grouped = {}
    for line in lines:
        grouped.setdefault(line["code"], []).append(line)
    return grouped


class Verification:
    def __init__(self):
        self._results = {}

    def compare(self, job, expected, actual):
        reasons = []
        actual_header = actual.get("header", {})
        for key, wanted in expected.get("header", {}).items():
            found = actual_header.get(key)
            if found != wanted:
                reasons.append(f"header {key}: {wanted!r} != {found!r}")

        want = _by_code(expected.get("lines", []))
        have = _by_code(actual.get("lines", []))
        for code in list(want) + [c for c in have if c not in want]:
            if len(want.get(code, ())) > 1 or len(have.get(code, ())) > 1:
                reasons.append(f"duplicate line {code}")
            elif code not in have:
                reasons.append(f"missing line {code}")
            elif code not in want:
                reasons.append(f"extra line {code}")
            else:
                reasons.extend(self._compare_line(code, want[code][0], have[code][0]))

        outcome = Mismatch(tuple(reasons)) if reasons else Match()
        self._results[job] = outcome
        return outcome

    @staticmethod
    def _compare_line(code, expected, actual):
        reasons = []
        reason = _differ(code, "qty", expected.get("qty"), actual.get("qty"))
        if reason:
            reasons.append(reason)
        if expected.get("price") is not None:
            reason = _differ(code, "price", expected["price"], actual.get("price"))
            if reason:
                reasons.append(reason)
        return reasons

    def result(self, job):
        return self._results.get(job)
