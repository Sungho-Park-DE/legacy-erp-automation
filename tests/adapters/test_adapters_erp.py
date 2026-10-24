from decimal import Decimal

import pytest

from app.adapters import FakeErpViewer, FakeRecipe, ViewerError
from app.adapters.ports import Document, ErpViewer, Open, Set


def replay(viewer, steps, answer=True, seen=None):
    for step in steps:
        if isinstance(step, Open):
            viewer.open_screen(step.screen)
        elif isinstance(step, Set):
            viewer.set_value(step.path, step.value)
        else:
            viewer.call(step.fn)
        while viewer.pending_dialog() is not None:
            if seen is not None:
                seen.append(viewer.pending_dialog())
            viewer.answer_dialog(answer)


def payload(save=True):
    return {
        "job": "Q-1",
        "lines": [
            {"code": "P-100", "name": "Widget small", "qty": 2, "price": Decimal("9.50")},
            {"code": "P-200", "name": "Gizmo set", "qty": 5, "price": None},
        ],
        "save": save,
    }


def typed_document():
    return Document(
        header={"ref": "Q-1"},
        lines=[
            {"code": "P-100", "qty": 2, "price": "9.50"},
            {"code": "P-200", "qty": 5, "price": None},
        ],
    )


def read_back(viewer, ref="Q-1"):
    replay(viewer, FakeRecipe().read_back_steps(ref))
    return viewer.read_back(ref)


def quote_screen_with_line(viewer):
    viewer.open_screen("QuoteScreen")
    viewer.call("new_form")
    viewer.set_value("header.ref", "Q-9")
    viewer.set_value("line[0].code", "P-100")
    viewer.set_value("line[0].qty", "1")
    viewer.call("fill_line")


def test_satisfies_port():
    viewer: ErpViewer = FakeErpViewer()
    for name in ("open_screen", "set_value", "call", "pending_dialog", "answer_dialog", "read_back", "reset"):
        assert callable(getattr(viewer, name))


def test_happy_path_read_back_equals_typed():
    viewer = FakeErpViewer()
    replay(viewer, FakeRecipe().steps(payload()))
    assert viewer.documents["Q-1"] == typed_document()
    assert read_back(viewer) == typed_document()
    assert viewer.dangerous_calls == []


def test_save_dialog_comes_first_then_saved():
    viewer = FakeErpViewer()
    replay(viewer, FakeRecipe().steps(payload(save=False)))
    viewer.call("save_form")
    assert viewer.pending_dialog() == "Save this form?"
    assert viewer.documents == {}
    viewer.answer_dialog(True)
    assert viewer.pending_dialog() == "Saved."
    assert viewer.documents["Q-1"] == typed_document()
    viewer.answer_dialog(True)
    assert viewer.pending_dialog() is None


def test_declining_save_stores_nothing():
    viewer = FakeErpViewer()
    replay(viewer, FakeRecipe().steps(payload(save=False)))
    viewer.call("save_form")
    viewer.answer_dialog(False)
    assert viewer.pending_dialog() is None
    assert viewer.documents == {}


def test_dry_run_stores_nothing():
    viewer = FakeErpViewer()
    replay(viewer, FakeRecipe().steps(payload(save=False)))
    assert viewer.documents == {}


def test_save_mode_lie_not_saved():
    viewer = FakeErpViewer(save_mode="lie_not_saved")
    seen = []
    replay(viewer, FakeRecipe().steps(payload()), seen=seen)
    assert seen == ["Save this form?", "Saved."]
    assert viewer.documents == {}
    replay(viewer, FakeRecipe().read_back_steps("Q-1"))
    assert viewer.read_back("Q-1") == Document(header={"ref": "Q-1"}, lines=[])


def test_save_mode_lie_altered():
    viewer = FakeErpViewer(save_mode="lie_altered")
    replay(viewer, FakeRecipe().steps(payload()))
    actual = read_back(viewer)
    assert actual.lines[0] == {"code": "P-100", "qty": 3, "price": "9.50"}
    assert actual.lines[1] == typed_document().lines[1]
    assert actual != typed_document()


def test_unknown_save_mode_is_rejected():
    with pytest.raises(ValueError):
        FakeErpViewer(save_mode="maybe")


def test_fail_on_function_raises_and_does_nothing():
    viewer = FakeErpViewer(fail_on=("fill_line",))
    viewer.open_screen("QuoteScreen")
    viewer.call("new_form")
    viewer.set_value("header.ref", "Q-9")
    viewer.set_value("line[0].code", "P-100")
    viewer.set_value("line[0].qty", "1")
    with pytest.raises(ViewerError):
        viewer.call("fill_line")
    assert ("QuoteScreen", "fill_line") not in viewer.calls_made


def test_fail_on_screen_name_fails_open():
    viewer = FakeErpViewer(fail_on=("ListScreen",))
    with pytest.raises(ViewerError):
        viewer.open_screen("ListScreen")
    assert viewer.current_screen == "HomeScreen"
    assert viewer.pending_dialog() is None


def test_fail_on_dangerous_function_is_not_recorded():
    viewer = FakeErpViewer(fail_on=("print_form",))
    quote_screen_with_line(viewer)
    with pytest.raises(ViewerError):
        viewer.call("print_form")
    assert viewer.dangerous_calls == []


def test_dialog_pending_blocks_call_and_open():
    viewer = FakeErpViewer()
    quote_screen_with_line(viewer)
    viewer.call("save_form")
    with pytest.raises(ViewerError, match="dialog pending"):
        viewer.call("fill_line")
    with pytest.raises(ViewerError, match="dialog pending"):
        viewer.open_screen("ListScreen")
    viewer.answer_dialog(True)
    with pytest.raises(ViewerError, match="dialog pending"):
        viewer.open_screen("ListScreen")
    viewer.answer_dialog(True)
    viewer.open_screen("HomeScreen")


def test_answer_without_dialog_raises():
    with pytest.raises(ViewerError):
        FakeErpViewer().answer_dialog(True)


def test_dialog_on_unknown_dialog_after_call_and_open():
    viewer = FakeErpViewer(dialog_on={"new_form": "Server is restarting in 5 minutes.", "HomeScreen": "Welcome."})
    viewer.open_screen("HomeScreen")
    assert viewer.pending_dialog() == "Welcome."
    viewer.answer_dialog(True)
    viewer.open_screen("QuoteScreen")
    assert viewer.pending_dialog() is None
    viewer.call("new_form")
    assert viewer.pending_dialog() == "Server is restarting in 5 minutes."


def test_loading_complete_after_open_list_and_refresh():
    viewer = FakeErpViewer()
    viewer.open_screen("ListScreen")
    assert viewer.pending_dialog() == "Loading complete."
    viewer.answer_dialog(True)
    viewer.call("refresh_list")
    assert viewer.pending_dialog() == "Loading complete."


def test_call_on_wrong_screen_and_unknown_screen():
    viewer = FakeErpViewer()
    with pytest.raises(ViewerError):
        viewer.call("save_form")
    with pytest.raises(ViewerError):
        viewer.open_screen("NoSuchScreen")
    with pytest.raises(ViewerError):
        viewer.open_screen("ItemPicker")
    viewer.open_screen("QuoteScreen")
    with pytest.raises(ViewerError):
        viewer.call("refresh_list")
    with pytest.raises(ViewerError):
        viewer.call("nothing")


def test_set_value_needs_form_and_known_path():
    viewer = FakeErpViewer()
    with pytest.raises(ViewerError):
        viewer.set_value("header.ref", "Q-1")
    viewer.open_screen("QuoteScreen")
    with pytest.raises(ViewerError):
        viewer.set_value("header.ref", "Q-1")
    viewer.call("new_form")
    with pytest.raises(ViewerError):
        viewer.set_value("header.colour", "red")
    viewer.set_value("header.ref", "Q-1")


def test_fill_line_needs_code_and_whole_qty():
    viewer = FakeErpViewer()
    viewer.open_screen("QuoteScreen")
    viewer.call("new_form")
    with pytest.raises(ViewerError):
        viewer.call("fill_line")
    viewer.set_value("line[0].code", "P-100")
    viewer.set_value("line[0].qty", "two")
    with pytest.raises(ViewerError):
        viewer.call("fill_line")


def test_picker_popup_roundtrip():
    viewer = FakeErpViewer()
    quote_screen_with_line(viewer)
    viewer.call("open_picker")
    assert viewer.current_screen == "ItemPicker"
    with pytest.raises(ViewerError):
        viewer.call("save_form")
    with pytest.raises(ViewerError):
        viewer.open_screen("HomeScreen")
    viewer.call("pick_item")
    viewer.call("close_picker")
    assert viewer.current_screen == "QuoteScreen"
    assert [fn for _, fn in viewer.calls_made[-3:]] == ["open_picker", "pick_item", "close_picker"]
    assert viewer.calls_made[-2] == ("ItemPicker", "pick_item")


def test_dangerous_print_has_real_effect_and_is_recorded():
    viewer = FakeErpViewer()
    quote_screen_with_line(viewer)
    viewer.call("print_form")
    assert viewer.pending_dialog() == "Print this form?"
    viewer.answer_dialog(True)
    assert viewer.printed == ["Q-9"]
    assert viewer.dangerous_calls == ["print_form"]


def test_dangerous_delete_removes_document():
    viewer = FakeErpViewer()
    replay(viewer, FakeRecipe().steps(payload()))
    viewer.call("delete_form")
    assert viewer.pending_dialog() == "Delete this document?"
    viewer.answer_dialog(True)
    assert viewer.documents == {}
    assert viewer.dangerous_calls == ["delete_form"]


def test_dangerous_finalize_locks_document():
    viewer = FakeErpViewer()
    replay(viewer, FakeRecipe().steps(payload()))
    viewer.call("finalize_form")
    assert viewer.pending_dialog() == "Finalize and lock this quote?"
    viewer.answer_dialog(True)
    assert "Q-1" in viewer.locked
    assert viewer.dangerous_calls == ["finalize_form"]
    with pytest.raises(ViewerError, match="locked"):
        viewer.call("save_form")


def test_dangerous_declined_has_no_effect_but_is_recorded():
    viewer = FakeErpViewer()
    replay(viewer, FakeRecipe().steps(payload()))
    for fn in ("print_form", "delete_form", "finalize_form"):
        viewer.call(fn)
        viewer.answer_dialog(False)
    assert viewer.printed == []
    assert "Q-1" in viewer.documents
    assert viewer.locked == set()
    assert viewer.dangerous_calls == ["print_form", "delete_form", "finalize_form"]


def test_reset_drops_form_dialog_and_screen():
    viewer = FakeErpViewer()
    quote_screen_with_line(viewer)
    viewer.call("save_form")
    viewer.reset()
    assert viewer.pending_dialog() is None
    assert viewer.current_screen == "HomeScreen"
    assert viewer.reset_count == 1
    assert viewer.documents == {}
    viewer.open_screen("QuoteScreen")
    with pytest.raises(ViewerError):
        viewer.set_value("header.ref", "Q-9")
    viewer.reset()
    assert viewer.reset_count == 2


def test_reset_keeps_stored_documents():
    viewer = FakeErpViewer()
    replay(viewer, FakeRecipe().steps(payload()))
    viewer.reset()
    assert "Q-1" in viewer.documents


def test_read_back_preconditions():
    viewer = FakeErpViewer()
    replay(viewer, FakeRecipe().steps(payload()))
    with pytest.raises(ViewerError):
        viewer.read_back("Q-1")
    replay(viewer, FakeRecipe().read_back_steps("Q-1"))
    assert viewer.read_back("Q-404") == Document(header={"ref": "Q-404"}, lines=[])
    assert viewer.read_back("Q-1").header == {"ref": "Q-1"}


def test_read_back_returns_a_copy():
    viewer = FakeErpViewer()
    replay(viewer, FakeRecipe().steps(payload()))
    document = read_back(viewer)
    document.lines[0]["qty"] = 99
    assert viewer.read_back("Q-1").lines[0]["qty"] == 2


def test_calls_made_records_screen_and_function():
    viewer = FakeErpViewer()
    replay(viewer, FakeRecipe().steps(payload(save=False)))
    assert viewer.calls_made == [
        ("QuoteScreen", "new_form"),
        ("QuoteScreen", "fill_line"),
        ("QuoteScreen", "fill_line"),
    ]
