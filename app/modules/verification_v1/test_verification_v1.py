from decimal import Decimal

from app.modules.verification_v1 import Match, Mismatch, Verification


def doc(lines, **header):
    return {"header": header, "lines": lines}


def test_operational_principle():
    v = Verification()
    expected = doc([{"code": "A", "qty": 2}, {"code": "B", "qty": 1}])

    same = doc([{"code": "A", "qty": 2}, {"code": "B", "qty": 1}])
    assert v.compare("j1", expected, same) == Match()

    other = doc([{"code": "A", "qty": 2}, {"code": "B", "qty": 3}])
    assert v.compare("j2", expected, other) == Mismatch(("qty B: 1 != 3",))

    assert v.result("j1") == Match()
    assert v.result("j2") == Mismatch(("qty B: 1 != 3",))
    assert v.result("unknown") is None


def test_effects_overwrite_result_per_job():
    v = Verification()
    expected = doc([{"code": "A", "qty": 1}])
    v.compare("j", expected, doc([]))
    assert isinstance(v.result("j"), Mismatch)
    v.compare("j", expected, expected)
    assert v.result("j") == Match()


def test_missing_and_extra_lines():
    v = Verification()
    expected = doc([{"code": "A", "qty": 1}, {"code": "C", "qty": 1}])
    actual = doc([{"code": "A", "qty": 1}, {"code": "D", "qty": 1}])
    result = v.compare("j", expected, actual)
    assert result == Mismatch(("missing line C", "extra line D"))


def test_order_of_lines_does_not_matter():
    v = Verification()
    expected = doc([{"code": "A", "qty": 1}, {"code": "B", "qty": 2}])
    actual = doc([{"code": "B", "qty": 2}, {"code": "A", "qty": 1}])
    assert v.compare("j", expected, actual) == Match()


def test_duplicate_line_is_a_mismatch_not_a_sum():
    v = Verification()
    expected = doc([{"code": "A", "qty": 2}])
    actual = doc([{"code": "A", "qty": 1}, {"code": "A", "qty": 1}])
    assert v.compare("j", expected, actual) == Mismatch(("duplicate line A",))
    assert v.compare("j", actual, expected) == Mismatch(("duplicate line A",))
    assert v.compare("j", actual, actual) == Mismatch(("duplicate line A",))


def test_quantity_is_numeric():
    v = Verification()
    expected = doc([{"code": "A", "qty": 2}, {"code": "B", "qty": "3"}])
    actual = doc([{"code": "A", "qty": "2.0"}, {"code": "B", "qty": 3.0}])
    assert v.compare("j", expected, actual) == Match()


def test_unreadable_quantity_is_a_mismatch():
    v = Verification()
    result = v.compare("j", doc([{"code": "A", "qty": 1}]), doc([{"code": "A", "qty": "many"}]))
    assert result == Mismatch(("qty A: 1 != 'many'",))


def test_price_equality_is_numeric():
    v = Verification()
    expected = doc([{"code": "A", "qty": 1, "price": "12.50"}, {"code": "B", "qty": 1, "price": 3}])
    actual = doc([{"code": "A", "qty": 1, "price": Decimal("12.5")}, {"code": "B", "qty": 1, "price": 3.0}])
    assert v.compare("j", expected, actual) == Match()


def test_price_mismatch_reason():
    v = Verification()
    expected = doc([{"code": "A", "qty": 1, "price": Decimal("12.50")}])
    actual = doc([{"code": "A", "qty": 1, "price": "13"}])
    assert v.compare("j", expected, actual) == Mismatch(("price A: 12.5 != 13",))


def test_price_compared_only_where_expected_has_one():
    v = Verification()
    expected = doc([{"code": "A", "qty": 1}, {"code": "B", "qty": 1, "price": None}])
    actual = doc([{"code": "A", "qty": 1, "price": "99"}, {"code": "B", "qty": 1, "price": "5"}])
    assert v.compare("j", expected, actual) == Match()


def test_expected_price_missing_in_actual_is_a_mismatch():
    v = Verification()
    result = v.compare("j", doc([{"code": "A", "qty": 1, "price": 5}]), doc([{"code": "A", "qty": 1}]))
    assert result == Mismatch(("price A: 5 != None",))


def test_header_keys_come_only_from_expected():
    v = Verification()
    expected = doc([], ref="x", customer="K1")
    assert v.compare("j", expected, doc([], ref="x", customer="K1", note="extra")) == Match()
    assert v.compare("j", doc([]), doc([], ref="anything")) == Match()


def test_header_mismatch_reasons():
    v = Verification()
    expected = doc([], ref="x", customer="K1")
    actual = doc([], ref="y")
    assert v.compare("j", expected, actual) == Mismatch(
        ("header ref: 'x' != 'y'", "header customer: 'K1' != None")
    )


def test_all_reasons_are_collected_in_order():
    v = Verification()
    expected = doc([{"code": "A", "qty": 1}, {"code": "B", "qty": 1, "price": 2}], ref="x")
    actual = doc([{"code": "A", "qty": 4}, {"code": "E", "qty": 1}], ref="z")
    assert v.compare("j", expected, actual) == Mismatch(
        ("header ref: 'x' != 'z'", "qty A: 1 != 4", "missing line B", "extra line E")
    )


def test_empty_documents_match():
    assert Verification().compare("j", doc([]), doc([])) == Match()
    assert Verification().compare("j", {"header": {}, "lines": []}, {"header": {}, "lines": []}) == Match()


def test_inputs_are_not_modified():
    expected = doc([{"code": "A", "qty": "2", "price": "1.0"}], ref="x")
    actual = doc([{"code": "A", "qty": 2, "price": 1}], ref="x")
    before = (repr(expected), repr(actual))
    Verification().compare("j", expected, actual)
    assert (repr(expected), repr(actual)) == before
