from decimal import Decimal

from app.modules.verification_v2 import (
    Found,
    Many,
    Match,
    Mismatch,
    NotFound,
    Verification,
)


def doc(lines, **header):
    return {"header": header, "lines": lines}


def test_operational_principle_locate():
    v = Verification()
    documents = [{"ref": "D1", "note": "J"}, {"ref": "D2", "note": "J"}]
    assert v.locate("J", documents, {"D1"}) == Found("D2")


def test_operational_principle_order_and_duplicates():
    v = Verification()
    expected = doc([{"code": "A", "qty": 2}, {"code": "B", "qty": 1}, {"code": "A", "qty": 1}])
    actual = doc([{"code": "A", "qty": "1"}, {"code": "B", "qty": Decimal("1.0")}, {"code": "A", "qty": 2}])
    assert v.compare("j", expected, actual) == Match()
    assert v.result("j") == Match()


def test_missing_and_extra():
    v = Verification()
    expected = doc([{"code": "A", "qty": 2}, {"code": "A", "qty": 2}])
    actual = doc([{"code": "A", "qty": "2.0"}, {"code": "C", "qty": 1}])
    assert v.compare("j", expected, actual) == Mismatch(("missing A x2", "extra C x1"))


def test_same_code_twice_differs_from_v1():
    """v1 refuses a repeated code ("duplicate line A"); v2 compares both lines."""
    v = Verification()
    lines = [{"code": "A", "qty": 1}, {"code": "A", "qty": 3}]
    assert v.compare("j", doc(lines), doc(list(reversed(lines)))) == Match()


def test_line_from_another_document_only_reason():
    v = Verification()
    expected = doc([{"code": "A", "qty": 1}], ref="D2")
    actual = doc([{"code": "A", "qty": 1, "ref": "D1"}, {"code": "Z", "qty": 9}], ref="D9")
    assert v.compare("j", expected, actual) == Mismatch(("line from another document D1",))


def test_line_with_own_ref_is_fine():
    v = Verification()
    expected = doc([{"code": "A", "qty": 1}], ref="D2")
    actual = doc([{"code": "A", "qty": 1, "ref": "D2"}], ref="D2")
    assert v.compare("j", expected, actual) == Match()


def test_header_mismatch():
    v = Verification()
    assert v.compare("j", doc([], ref="x"), doc([], ref="y")) == Mismatch(("header ref: 'x' != 'y'",))


def test_price():
    v = Verification()
    expected = doc([{"code": "A", "qty": 1, "price": "12.50"}, {"code": "B", "qty": 1}])
    ok = doc([{"code": "A", "qty": 1, "price": Decimal("12.5")}, {"code": "B", "qty": 1, "price": 99}])
    assert v.compare("j", expected, ok) == Match()
    bad = doc([{"code": "A", "qty": 1, "price": 13}, {"code": "B", "qty": 1}])
    assert v.compare("j", expected, bad) == Mismatch(("price A: 12.5 != 13",))
    none = doc([{"code": "A", "qty": 1}, {"code": "B", "qty": 1}])
    assert v.compare("j", expected, none) == Mismatch(("price A: 12.5 != None",))


def test_price_matches_any_line_with_same_code_and_qty():
    v = Verification()
    expected = doc([{"code": "A", "qty": 1, "price": 5}, {"code": "A", "qty": 1, "price": 7}])
    actual = doc([{"code": "A", "qty": 1, "price": 7}, {"code": "A", "qty": 1, "price": 5}])
    assert v.compare("j", expected, actual) == Match()


def test_locate_none_and_many():
    v = Verification()
    assert v.locate("J", [{"ref": "D1", "note": "J"}], {"D1"}) == NotFound()
    documents = [{"ref": "D3", "note": "J"}, {"ref": "D2", "note": "J"}]
    assert v.locate("J", documents, set()) == Many(("D2", "D3"))


def test_locate_ignores_other_notes_and_missing_note():
    v = Verification()
    documents = [{"ref": "D1"}, {"ref": "D2", "note": "K"}, {"ref": "D3", "note": "J"}]
    assert v.locate("J", documents, set()) == Found("D3")


def test_result_unknown_job():
    assert Verification().result("nope") is None
