from dataclasses import dataclass
from decimal import Decimal, InvalidOperation

__all__ = ["Steps", "Stop", "Ok", "plan", "may_confirm_removal", "check_requests"]


@dataclass(frozen=True)
class Steps:
    ops: tuple


@dataclass(frozen=True)
class Stop:
    reason: str
    diffs: tuple = ()


@dataclass(frozen=True)
class Ok:
    pass


def _number(value):
    try:
        number = Decimal(str(value).strip())
    except InvalidOperation:
        return None
    return number if number.is_finite() else None


def _same(left, right):
    a, b = _number(left), _number(right)
    if a is None or b is None:
        return left == right
    return a == b


def _show(value):
    number = _number(value)
    return str(value) if number is None else format(number.normalize(), "f")


def _has_duplicates(lines):
    codes = [line["code"] for line in lines]
    return len(codes) != len(set(codes))


def plan(base, current, target):
    if not current or not current.get("lines"):
        return Stop("not found")
    if (current.get("header") or {}).get("status") == "locked":
        return Stop("locked")
    lines = current["lines"]
    if any(_has_duplicates(group) for group in (base, lines, target)):
        return Stop("duplicate code")

    saved = {line["code"]: line for line in base}
    now = {line["code"]: line for line in lines}
    diffs = []
    for code, line in saved.items():
        if code not in now:
            diffs.append(f"missing {code}")
        elif not _same(line["qty"], now[code]["qty"]):
            diffs.append(f"qty {code}: {_show(line['qty'])} != {_show(now[code]['qty'])}")
    diffs.extend(f"extra {code}" for code in now if code not in saved)
    if diffs:
        return Stop("changed since saved", tuple(diffs))

    wanted = {line["code"]: line for line in target}
    removes = [{"op": "remove", "code": c} for c in saved if c not in wanted]
    changes = [
        {"op": "qty", "code": c, "qty": line["qty"]}
        for c, line in wanted.items()
        if c in saved and not _same(line["qty"], saved[c]["qty"])
    ]
    adds = []
    for c, line in wanted.items():
        if c not in saved:
            op = {"op": "add", "code": c, "qty": line["qty"]}
            if line.get("price") is not None:
                op["price"] = line["price"]
            adds.append(op)
    ops = tuple(removes + changes + adds)
    return Steps(ops) if ops else Stop("nothing to change")


def may_confirm_removal(named, removing):
    if not named or not removing:
        return False
    left, right = named.strip().upper(), removing.strip().upper()
    return bool(left) and left == right


def check_requests(log, update, dangerous):
    for name in log:
        if name in dangerous:
            return Stop(f"dangerous request {name}")
    count = sum(1 for name in log if name == update)
    if count != 1:
        return Stop(f"update sent {count} times")
    return Ok()
