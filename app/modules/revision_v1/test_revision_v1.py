from app.modules.revision_v1 import Ok, Steps, Stop, check_requests, may_confirm_removal, plan

BASE = [{"code": "A", "qty": 2}, {"code": "B", "qty": 1}]


def doc(lines, status=None):
    header = {"ref": "SO-1"}
    if status:
        header["status"] = status
    return {"header": header, "lines": lines}


def test_principle_single_qty_step():
    target = [{"code": "A", "qty": 3}, {"code": "B", "qty": 1}]
    assert plan(BASE, doc(BASE), target) == Steps(({"op": "qty", "code": "A", "qty": 3},))


def test_quantities_compare_as_numbers():
    current = doc([{"code": "B", "qty": "1.0"}, {"code": "A", "qty": "2"}])
    target = [{"code": "A", "qty": "2"}, {"code": "B", "qty": 1}]
    assert plan(BASE, current, target) == Stop("nothing to change")


def test_not_found():
    assert plan(BASE, None, BASE) == Stop("not found")
    assert plan(BASE, doc([]), BASE) == Stop("not found")


def test_locked():
    assert plan(BASE, doc(BASE, "locked"), BASE) == Stop("locked")


def test_duplicate_code_in_each_input():
    dup = [{"code": "A", "qty": 1}, {"code": "A", "qty": 2}]
    assert plan(dup, doc(BASE), BASE) == Stop("duplicate code")
    assert plan(BASE, doc(dup), BASE) == Stop("duplicate code")
    assert plan(BASE, doc(BASE), dup) == Stop("duplicate code")


def test_changed_since_saved_with_diffs():
    current = doc([{"code": "B", "qty": 5}, {"code": "C", "qty": 1}])
    result = plan(BASE, current, BASE)
    assert result == Stop("changed since saved", ("missing A", "qty B: 1 != 5", "extra C"))


def test_nothing_to_change():
    assert plan(BASE, doc(BASE), BASE) == Stop("nothing to change")


def test_stop_order_locked_before_duplicate():
    dup = [{"code": "A", "qty": 1}, {"code": "A", "qty": 2}]
    assert plan(dup, doc(BASE, "locked"), BASE) == Stop("locked")


def test_op_order_and_price_passthrough():
    base = [{"code": "A", "qty": 1}, {"code": "B", "qty": 1}, {"code": "C", "qty": 1}, {"code": "D", "qty": 1}]
    target = [
        {"code": "X", "qty": 2, "price": "9.5"},
        {"code": "D", "qty": 4},
        {"code": "Y", "qty": 1, "price": None},
        {"code": "B", "qty": 3},
        {"code": "C", "qty": 1},
    ]
    assert plan(base, doc(base), target).ops == (
        {"op": "remove", "code": "A"},
        {"op": "qty", "code": "D", "qty": 4},
        {"op": "qty", "code": "B", "qty": 3},
        {"op": "add", "code": "X", "qty": 2, "price": "9.5"},
        {"op": "add", "code": "Y", "qty": 1},
    )


def test_may_confirm_removal():
    assert may_confirm_removal(" b ", "B")
    assert not may_confirm_removal("A", "B")
    assert not may_confirm_removal(None, "B")
    assert not may_confirm_removal("B", None)
    assert not may_confirm_removal("", "")


def test_check_requests():
    danger = {"DeleteOrder"}
    assert check_requests(["Read", "Update"], "Update", danger) == Ok()
    assert check_requests(["Read"], "Update", danger) == Stop("update sent 0 times")
    assert check_requests(["Update", "Update"], "Update", danger) == Stop("update sent 2 times")
    assert check_requests(["Update", "DeleteOrder"], "Update", danger) == Stop("dangerous request DeleteOrder")
