import json
from decimal import Decimal
from itertools import product
from pathlib import Path

import pytest

from app.adapters import FakeErpViewer, FakeRecipe, SimulatedCrash, ViewerError
from app.adapters.fake_erp import DANGEROUS, FUNCTIONS, POPUP, SCREENS
from app.adapters.ports import Call, Document, Open, Set
from app.modules.actionpolicy_v1 import ActionPolicy, Allow

from tests.adapters.test_adapters_erp import payload, replay

POLICY = Path(__file__).resolve().parents[2] / "app" / "data" / "policy.json"


def saved_viewer(**kwargs):
    viewer = FakeErpViewer(**kwargs)
    replay(viewer, FakeRecipe().steps(payload()))
    return viewer


def on_list(viewer):
    replay(viewer, [Open("ListScreen")])
    return viewer


def loaded(viewer, ref="Q-1"):
    replay(viewer, [Open("EditScreen"), Set("header.ref", ref), Call("load_document")])
    return viewer


# numbering


def test_numbering_bot_is_default_and_unchanged():
    viewer = saved_viewer()
    assert viewer.documents["Q-1"].header == {"ref": "Q-1"}


def test_numbering_erp_assigns_refs_and_keeps_typed_ref_as_note():
    viewer = FakeErpViewer(numbering="erp")
    replay(viewer, FakeRecipe().steps(payload()))
    replay(viewer, FakeRecipe().steps(payload()))
    assert list(viewer.documents) == ["D-0001", "D-0002"]
    assert viewer.documents["D-0001"].header == {"ref": "D-0001", "note": "Q-1"}
    assert viewer.documents["D-0002"].lines[0]["code"] == "P-100"


def test_unknown_numbering_is_rejected():
    with pytest.raises(ValueError):
        FakeErpViewer(numbering="maybe")


# list_documents and locked status


def test_list_documents_only_on_list_screen():
    viewer = saved_viewer()
    with pytest.raises(ViewerError):
        viewer.list_documents()
    assert on_list(viewer).list_documents() == [Document(header={"ref": "Q-1"}, lines=[])]


def test_list_documents_insertion_order_and_copies():
    viewer = FakeErpViewer(numbering="erp")
    for _ in range(3):
        replay(viewer, FakeRecipe().steps(payload()))
    listed = on_list(viewer).list_documents()
    assert [d.header["ref"] for d in listed] == ["D-0001", "D-0002", "D-0003"]
    listed[0].header["ref"] = "X"
    assert viewer.list_documents()[0].header["ref"] == "D-0001"


def test_locked_status_shown_in_list_and_read_back():
    viewer = saved_viewer()
    viewer.call("finalize_form")
    viewer.answer_dialog(True)
    on_list(viewer)
    assert viewer.list_documents()[0].header == {"ref": "Q-1", "status": "locked"}
    assert viewer.read_back("Q-1").header == {"ref": "Q-1", "status": "locked"}
    assert viewer.documents["Q-1"].header == {"ref": "Q-1"}


# request log


def test_request_log_names_each_request():
    viewer = saved_viewer(extra_request="audit")
    replay(viewer, [Open("ListScreen"), Call("refresh_list")])
    loaded(viewer)
    replay(viewer, [Set("edit.code", "P-200"), Set("edit.qty", "1"), Call("set_line_qty"), Call("update_form")])
    replay(viewer, [Call("finalize_form"), Call("delete_form")])
    assert viewer.request_log() == ["save", "list", "list", "load", "update", "audit", "finalize", "delete"]


def test_request_log_print_and_declined_dialogs():
    viewer = FakeErpViewer()
    replay(viewer, FakeRecipe().steps(payload(save=False)), answer=False)
    viewer.call("save_form")
    viewer.answer_dialog(False)
    viewer.call("print_form")
    viewer.answer_dialog(True)
    assert viewer.request_log() == ["print"]


def test_request_log_is_a_copy_and_lie_not_saved_logs_no_save():
    viewer = saved_viewer(save_mode="lie_not_saved")
    log = viewer.request_log()
    log.append("x")
    assert viewer.request_log() == []


# EditScreen


def test_edit_screen_set_value_paths():
    viewer = saved_viewer()
    viewer.open_screen("EditScreen")
    for path in ("header.ref", "edit.code", "edit.qty", "edit.price"):
        viewer.set_value(path, "1")
    with pytest.raises(ViewerError):
        viewer.set_value("line[0].code", "P-100")


def test_load_document_needs_existing_document():
    viewer = saved_viewer()
    viewer.open_screen("EditScreen")
    with pytest.raises(ViewerError):
        viewer.call("load_document")
    viewer.set_value("header.ref", "Q-404")
    with pytest.raises(ViewerError):
        viewer.call("load_document")
    with pytest.raises(ViewerError):
        viewer.call("update_form")


def test_remove_line_dialog_and_effect():
    viewer = loaded(saved_viewer())
    viewer.set_value("edit.code", "P-200")
    viewer.call("remove_line")
    assert viewer.pending_dialog() == "Remove item P-200 from this document?"
    viewer.answer_dialog(True)
    replay(viewer, [Call("update_form")])
    assert [line["code"] for line in viewer.documents["Q-1"].lines] == ["P-100"]


def test_remove_line_declined_keeps_line_and_unknown_code_fails():
    viewer = loaded(saved_viewer())
    viewer.set_value("edit.code", "P-999")
    with pytest.raises(ViewerError):
        viewer.call("remove_line")
    viewer.set_value("edit.code", "P-200")
    viewer.call("remove_line")
    viewer.answer_dialog(False)
    replay(viewer, [Call("update_form")])
    assert len(viewer.documents["Q-1"].lines) == 2


def test_remove_line_dialog_can_name_another_item():
    viewer = loaded(saved_viewer(name_in_removal="P-100"))
    viewer.set_value("edit.code", "P-200")
    viewer.call("remove_line")
    assert viewer.pending_dialog() == "Remove item P-100 from this document?"


def test_set_line_qty():
    viewer = loaded(saved_viewer())
    viewer.set_value("edit.code", "P-100")
    viewer.set_value("edit.qty", "two")
    with pytest.raises(ViewerError):
        viewer.call("set_line_qty")
    viewer.set_value("edit.qty", "7")
    viewer.call("set_line_qty")
    assert viewer.pending_dialog() is None
    assert viewer.documents["Q-1"].lines[0]["qty"] == 2
    replay(viewer, [Call("update_form")])
    assert viewer.documents["Q-1"].lines[0] == {"code": "P-100", "qty": 7, "price": "9.50"}


def test_add_line_with_and_without_price_and_refuses_duplicate():
    viewer = loaded(saved_viewer())
    viewer.set_value("edit.code", "P-100")
    viewer.set_value("edit.qty", "1")
    with pytest.raises(ViewerError):
        viewer.call("add_line")
    replay(viewer, [Set("edit.code", "P-300"), Call("add_line")])
    replay(viewer, [Set("edit.code", "P-400"), Set("edit.price", "1.25"), Call("add_line"), Call("update_form")])
    assert viewer.documents["Q-1"].lines[2:] == [
        {"code": "P-300", "qty": 1, "price": None},
        {"code": "P-400", "qty": 1, "price": "1.25"},
    ]


def test_update_form_dialogs_and_keeps_header():
    viewer = loaded(saved_viewer(numbering="erp"), ref="D-0001")
    viewer.call("update_form")
    assert viewer.pending_dialog() == "Save changes to this document?"
    viewer.answer_dialog(True)
    assert viewer.pending_dialog() == "Saved."
    viewer.answer_dialog(True)
    assert viewer.documents["D-0001"].header == {"ref": "D-0001", "note": "Q-1"}


def test_update_form_declined_stores_nothing():
    viewer = loaded(saved_viewer())
    replay(viewer, [Set("edit.code", "P-200"), Call("remove_line")])
    viewer.call("update_form")
    viewer.answer_dialog(False)
    assert viewer.pending_dialog() is None
    assert len(viewer.documents["Q-1"].lines) == 2
    assert "update" not in viewer.request_log()


def test_update_form_on_locked_document_raises_at_call_time():
    viewer = saved_viewer()
    replay(viewer, [Call("finalize_form")])
    loaded(viewer)
    with pytest.raises(ViewerError, match="locked"):
        viewer.call("update_form")
    assert viewer.pending_dialog() is None


def test_dangerous_functions_on_edit_screen_are_recorded():
    viewer = loaded(saved_viewer())
    replay(viewer, [Call("finalize_form"), Call("delete_form")], answer=False)
    assert viewer.dangerous_calls == ["finalize_form", "delete_form"]
    replay(viewer, [Call("delete_form")])
    assert viewer.documents == {}


def test_reset_drops_edit_state():
    viewer = loaded(saved_viewer())
    viewer.reset()
    viewer.open_screen("EditScreen")
    with pytest.raises(ViewerError):
        viewer.call("update_form")


def test_edit_by_person_replaces_lines():
    viewer = saved_viewer()
    viewer.edit_by_person("Q-1", [{"code": "P-900", "qty": 1, "price": None}])
    assert viewer.documents["Q-1"] == Document(header={"ref": "Q-1"}, lines=[{"code": "P-900", "qty": 1, "price": None}])


# crash after save


def test_simulated_crash_is_not_an_exception():
    assert issubclass(SimulatedCrash, BaseException)
    assert not issubclass(SimulatedCrash, Exception)


def test_crash_after_save_form_stores_then_crashes():
    viewer = FakeErpViewer(crash_after_save=True)
    replay(viewer, FakeRecipe().steps(payload(save=False)))
    viewer.call("save_form")
    with pytest.raises(SimulatedCrash):
        viewer.answer_dialog(True)
    assert "Q-1" in viewer.documents
    assert viewer.request_log() == ["save"]
    assert viewer.pending_dialog() is None


def test_crash_after_update_form_stores_then_crashes():
    viewer = FakeErpViewer(crash_after_save=True)
    viewer.documents["Q-1"] = Document(header={"ref": "Q-1"}, lines=[{"code": "P-100", "qty": 1, "price": None}])
    loaded(viewer)
    replay(viewer, [Set("edit.code", "P-100"), Set("edit.qty", "4"), Call("set_line_qty")])
    viewer.call("update_form")
    with pytest.raises(SimulatedCrash):
        viewer.answer_dialog(True)
    assert viewer.documents["Q-1"].lines[0]["qty"] == 4
    assert viewer.request_log()[-1] == "update"


def test_crash_not_triggered_when_declined():
    viewer = FakeErpViewer(crash_after_save=True)
    replay(viewer, FakeRecipe().steps(payload()), answer=False)
    assert viewer.documents == {}


# recipe edit steps against the viewer


def test_edit_steps_round_trip():
    viewer = saved_viewer()
    ops = [
        {"op": "remove", "code": "P-200"},
        {"op": "qty", "code": "P-100", "qty": 3},
        {"op": "add", "code": "P-300", "qty": 2, "price": Decimal("4.00")},
    ]
    seen = []
    replay(viewer, FakeRecipe().edit_steps("Q-1", ops), seen=seen)
    assert seen == ["Remove item P-200 from this document?", "Save changes to this document?", "Saved."]
    assert viewer.documents["Q-1"].lines == [
        {"code": "P-100", "qty": 3, "price": "9.50"},
        {"code": "P-300", "qty": 2, "price": "4.00"},
    ]
    assert viewer.dangerous_calls == []


# policy: dangerous functions are never allowed


def loaded_policy():
    policy = ActionPolicy()
    policy.load(json.loads(POLICY.read_text(encoding="utf-8")))
    return policy


def test_policy_never_allows_dangerous_functions_anywhere():
    policy = loaded_policy()
    for screen, fn, allow_save, saving in product((*SCREENS, POPUP), DANGEROUS, (True, False), (True, False)):
        assert policy.check_call(screen, fn, allow_save, saving) != Allow(), (screen, fn, allow_save, saving)


def test_policy_allows_every_edit_screen_function_except_dangerous():
    policy = loaded_policy()
    assert policy.check_screen("EditScreen") == Allow()
    for fn in FUNCTIONS["EditScreen"]:
        expected = fn not in DANGEROUS
        assert (policy.check_call("EditScreen", fn, True, fn == "update_form") == Allow()) is expected, fn
    assert policy.check_call("EditScreen", "update_form", True, False) != Allow()
    assert policy.check_call("EditScreen", "update_form", False, True) != Allow()


def test_policy_edit_dialogs():
    from app.modules.actionpolicy_v1 import Accept, Stop

    policy = loaded_policy()
    assert policy.classify_dialog("Save changes to this document?", True, "update_form") == Accept()
    assert isinstance(policy.classify_dialog("Save changes to this document?", False, "update_form"), Stop)
    assert isinstance(policy.classify_dialog("Save changes to this document?", True, "remove_line"), Stop)
    assert policy.classify_dialog("Remove item P-200 from this document?", False, "remove_line") == Accept()
    assert isinstance(policy.classify_dialog("Remove item P-200 from this document?", False, "update_form"), Stop)
