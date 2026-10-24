import itertools
import json
from pathlib import Path

import pytest

from app.modules.actionpolicy_v1 import (
    Accept,
    ActionPolicy,
    Allow,
    Deny,
    Reject,
    Stop,
)

POLICY_FILE = Path(__file__).resolve().parents[2] / "data" / "policy.json"
FORBIDDEN_FUNCTIONS = ["print_form", "delete_form", "finalize_form", "reprint", "Discard_all", "x_DELETE_y"]


def real_rules():
    return json.loads(POLICY_FILE.read_text(encoding="utf-8"))


def real_policy():
    policy = ActionPolicy()
    policy.load(real_rules())
    return policy


def small_rules(**changes):
    rules = {
        "screens": ["Q"],
        "popups": {},
        "calls": {"Q": ["fill_line", "save"]},
        "save_calls": ["save"],
        "forbidden": ["delete", "print"],
        "dialogs": [],
    }
    rules.update(changes)
    return rules


def small_policy(**changes):
    policy = ActionPolicy()
    policy.load(small_rules(**changes))
    return policy


def test_operational_principle():
    policy = real_policy()

    assert policy.check_screen("QuoteScreen") == Allow()
    assert policy.check_call("QuoteScreen", "fill_line", allow_save=False, saving=False) == Allow()
    assert isinstance(policy.check_call("QuoteScreen", "print_form", allow_save=True, saving=True), Deny)

    assert isinstance(policy.check_call("QuoteScreen", "save_form", allow_save=False, saving=True), Deny)
    assert isinstance(policy.check_call("QuoteScreen", "save_form", allow_save=True, saving=False), Deny)
    assert policy.check_call("QuoteScreen", "save_form", allow_save=True, saving=True) == Allow()

    assert policy.classify_dialog("Delete this document?", saving=False) == Reject()
    assert policy.classify_dialog("Saved.", saving=True, during="save_form") == Accept()
    assert isinstance(policy.classify_dialog("Unexpected error 0x2A", saving=False), Stop)


def test_real_policy_dialogs():
    policy = real_policy()
    assert policy.classify_dialog("Save this form?", saving=True, during="save_form") == Accept()
    assert policy.classify_dialog("Saved.", saving=True) == Accept()
    assert policy.classify_dialog("Loading complete.", saving=False) == Accept()
    assert policy.classify_dialog("Loading complete.", saving=True, during="save_form") == Accept()
    for text in ["Delete this document?", "Print this form?", "Finalize and lock this quote?"]:
        assert policy.classify_dialog(text, saving=False) == Reject()
        assert policy.classify_dialog(text, saving=True, during="save_form") == Reject()
    for text in ["Server is restarting in 5 minutes.", "Unexpected error 0x2A", ""]:
        assert isinstance(policy.classify_dialog(text, saving=False), Stop)


def test_real_policy_vocabulary():
    rules = real_policy().rules()
    assert rules["screens"] == ["HomeScreen", "ListScreen", "QuoteScreen"]
    assert rules["popups"] == {"ItemPicker": {"parent": "QuoteScreen", "opener": "open_picker"}}
    assert rules["calls"]["HomeScreen"] == []
    assert rules["calls"]["QuoteScreen"] == ["fill_line", "new_form", "open_picker", "save_form"]
    assert rules["calls"]["ItemPicker"] == ["close_picker", "pick_item"]
    assert rules["calls"]["ListScreen"] == ["open_row", "refresh_list"]
    assert rules["save_calls"] == ["save_form"]
    assert rules["forbidden"] == ["delete", "discard", "finalize", "print"]


def test_check_screen_requires_known_screen():
    policy = small_policy()
    assert policy.check_screen("Q") == Allow()
    deny = policy.check_screen("Other")
    assert isinstance(deny, Deny) and "Other" in deny.reason


def test_popup_only_via_right_parent_and_opener():
    policy = real_policy()
    assert policy.check_screen("ItemPicker", parent="QuoteScreen", opener="open_picker") == Allow()
    for parent, opener in [
        (None, None),
        ("QuoteScreen", None),
        (None, "open_picker"),
        ("ListScreen", "open_picker"),
        ("QuoteScreen", "open_row"),
        ("HomeScreen", "refresh_list"),
    ]:
        assert isinstance(policy.check_screen("ItemPicker", parent=parent, opener=opener), Deny)


def test_check_call_requires_screen_and_listing():
    policy = small_policy()
    assert policy.check_call("Q", "fill_line", allow_save=False, saving=False) == Allow()
    assert isinstance(policy.check_call("Q", "other", allow_save=True, saving=True), Deny)
    assert isinstance(policy.check_call("Elsewhere", "fill_line", allow_save=True, saving=True), Deny)


@pytest.mark.parametrize("allow_save,saving", list(itertools.product([True, False], repeat=2)))
def test_save_call_needs_both_allow_save_and_saving(allow_save, saving):
    result = real_policy().check_call("QuoteScreen", "save_form", allow_save=allow_save, saving=saving)
    assert (result == Allow()) == (allow_save and saving)


def test_save_call_is_not_allowed_on_another_screen():
    result = real_policy().check_call("ListScreen", "save_form", allow_save=True, saving=True)
    assert isinstance(result, Deny)


def test_never_allow_unlisted_or_forbidden_functions():
    policy = real_policy()
    screens = ["HomeScreen", "QuoteScreen", "ListScreen", "ItemPicker", "Unknown", "", "Q"]
    functions = FORBIDDEN_FUNCTIONS + ["save_form_print", "delete", "new_form_delete"]
    for screen, allow_save, saving, fn in itertools.product(screens, [True, False], [True, False], functions):
        result = policy.check_call(screen, fn, allow_save=allow_save, saving=saving)
        assert not isinstance(result, Allow), (screen, allow_save, saving, fn)


def test_never_allow_forbidden_function_even_if_rules_slip_through():
    policy = small_policy()
    policy._calls["Q"].add("print_form")
    assert isinstance(policy.check_call("Q", "print_form", allow_save=True, saving=True), Deny)


def test_never_allow_unknown_screens_or_unopened_popups():
    policy = real_policy()
    parents = [None, "QuoteScreen", "HomeScreen", "ListScreen", "ItemPicker", "Unknown"]
    openers = [None, "open_picker", "open_row", "save_form", "print_form"]
    for screen, parent, opener in itertools.product(["Unknown", "", "ItemPicker2", "Q"], parents, openers):
        assert isinstance(policy.check_screen(screen, parent=parent, opener=opener), Deny)
    for parent, opener in itertools.product(parents, openers):
        allowed = parent == "QuoteScreen" and opener == "open_picker"
        result = policy.check_screen("ItemPicker", parent=parent, opener=opener)
        assert (result == Allow()) == allowed


def test_question_with_forbidden_word_is_rejected_even_if_a_rule_accepts():
    rules = small_rules(
        dialogs=[{"pattern": ".*", "answer": "accept", "when": "always"}],
    )
    policy = ActionPolicy()
    policy.load(rules)
    assert policy.classify_dialog("Delete this document?", saving=True) == Reject()
    assert policy.classify_dialog("Really PRINT everything?", saving=False) == Reject()
    assert policy.classify_dialog("Is it fine?", saving=False) == Accept()


def test_forbidden_word_without_question_goes_through_rules():
    rules = small_rules(dialogs=[{"pattern": "Print job finished\\.", "answer": "accept", "when": "always"}])
    policy = ActionPolicy()
    policy.load(rules)
    assert policy.classify_dialog("Print job finished.", saving=False) == Accept()
    assert isinstance(policy.classify_dialog("Print job failed.", saving=False), Stop)


def test_reject_rule_beats_accept_rule_for_same_text():
    rules = small_rules(
        dialogs=[
            {"pattern": "Go on\\?", "answer": "accept", "when": "always"},
            {"pattern": "Go on\\?", "answer": "reject", "when": "always"},
        ],
    )
    policy = ActionPolicy()
    policy.load(rules)
    assert policy.classify_dialog("Go on?", saving=False) == Reject()


def test_unknown_dialog_stops_with_reason():
    stop = real_policy().classify_dialog("Server is restarting in 5 minutes.", saving=False)
    assert isinstance(stop, Stop) and "Server is restarting" in stop.reason


def test_dialog_rule_when_saving_and_during():
    policy = real_policy()
    assert isinstance(policy.classify_dialog("Saved.", saving=False), Stop)
    assert isinstance(policy.classify_dialog("Save this form?", saving=False, during="save_form"), Stop)
    assert isinstance(policy.classify_dialog("Save this form?", saving=True, during="fill_line"), Stop)
    assert isinstance(policy.classify_dialog("Save this form?", saving=True), Stop)


def test_dialog_pattern_must_match_whole_text():
    policy = real_policy()
    assert isinstance(policy.classify_dialog("Loading complete. Now shutting down.", saving=False), Stop)
    assert isinstance(policy.classify_dialog("Saved. Also deleted.", saving=True), Stop)


def test_classify_dialog_has_no_effects():
    policy = real_policy()
    before = policy.rules()
    for _ in range(3):
        assert policy.classify_dialog("Saved.", saving=True) == Accept()
    assert policy.rules() == before


def test_load_rejects_save_call_not_in_calls():
    with pytest.raises(ValueError, match="save"):
        ActionPolicy().load(small_rules(save_calls=["commit"]))


def test_load_rejects_forbidden_word_in_function_name():
    with pytest.raises(ValueError, match="print"):
        ActionPolicy().load(small_rules(calls={"Q": ["save", "Print_form"]}))
    with pytest.raises(ValueError, match="print"):
        ActionPolicy().load(small_rules(calls={"Q": ["save", "x"]}, popups={"P": {"parent": "Q", "opener": "go_print"}}))


def test_load_rejects_bad_dialog_rules():
    with pytest.raises(ValueError):
        ActionPolicy().load(small_rules(dialogs=[{"pattern": "(", "answer": "accept", "when": "always"}]))
    with pytest.raises(ValueError):
        ActionPolicy().load(small_rules(dialogs=[{"pattern": "x", "answer": "maybe", "when": "always"}]))
    with pytest.raises(ValueError):
        ActionPolicy().load(small_rules(dialogs=[{"pattern": "x", "answer": "accept", "when": "sometimes"}]))


def test_failed_load_keeps_previous_rules():
    policy = small_policy()
    with pytest.raises(ValueError):
        policy.load(small_rules(save_calls=["commit"]))
    assert policy.check_screen("Q") == Allow()


def test_empty_policy_allows_nothing():
    policy = ActionPolicy()
    assert isinstance(policy.check_screen("HomeScreen"), Deny)
    assert isinstance(policy.check_call("HomeScreen", "new_form", allow_save=True, saving=True), Deny)
    assert isinstance(policy.classify_dialog("Saved.", saving=True), Stop)


def test_rules_query_returns_copy_for_showing():
    policy = real_policy()
    shown = policy.rules()
    json.dumps(shown)
    shown["screens"].append("EvilScreen")
    shown["calls"]["HomeScreen"].append("print_form")
    assert isinstance(policy.check_screen("EvilScreen"), Deny)
    assert isinstance(policy.check_call("HomeScreen", "print_form", allow_save=True, saving=True), Deny)
