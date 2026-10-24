from decimal import Decimal

from app.adapters import FakeRecipe
from app.adapters.fake_erp import DANGEROUS
from app.adapters.ports import Call, ErpRecipe, Open, Set


def payload(save):
    return {
        "job": "Q-7",
        "lines": [
            {"code": "P-100", "name": "Widget small", "qty": 2, "price": Decimal("9.50")},
            {"code": "P-200", "name": "Gizmo set", "qty": 5, "price": None},
        ],
        "save": save,
    }


def test_satisfies_port():
    recipe: ErpRecipe = FakeRecipe()
    for name in ("steps", "read_back_steps", "read_back_ref"):
        assert callable(getattr(recipe, name))


def test_steps_with_save():
    assert FakeRecipe().steps(payload(True)) == [
        Open("QuoteScreen"),
        Call("new_form"),
        Set("header.ref", "Q-7"),
        Set("line[0].code", "P-100"),
        Set("line[0].qty", "2"),
        Set("line[0].price", "9.50"),
        Call("fill_line"),
        Set("line[1].code", "P-200"),
        Set("line[1].qty", "5"),
        Call("fill_line"),
        Call("save_form", is_save=True),
    ]


def test_steps_dry_run_has_no_save():
    steps = FakeRecipe().steps(payload(False))
    assert Call("save_form", is_save=True) not in steps
    assert not any(isinstance(s, Call) and s.is_save for s in steps)


def test_price_is_plain_decimal_string():
    p = payload(False)
    p["lines"][0]["price"] = Decimal("1E+2")
    assert Set("line[0].price", "100") in FakeRecipe().steps(p)


def test_never_emits_dangerous_functions_or_popups():
    for save in (True, False):
        steps = FakeRecipe().steps(payload(save))
        calls = {s.fn for s in steps if isinstance(s, Call)}
        assert not calls & set(DANGEROUS)
        assert not calls & {"open_picker", "pick_item", "close_picker"}
        assert all(s.screen != "ItemPicker" for s in steps if isinstance(s, Open))


def test_only_save_step_is_marked_as_save():
    saves = [s for s in FakeRecipe().steps(payload(True)) if isinstance(s, Call) and s.is_save]
    assert [s.fn for s in saves] == ["save_form"]


def test_read_back():
    recipe = FakeRecipe()
    assert recipe.read_back_steps("Q-7") == [Open("ListScreen"), Call("refresh_list")]
    assert recipe.read_back_ref("Q-7") == "Q-7"
