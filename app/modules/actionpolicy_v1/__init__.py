import copy
import re
from dataclasses import dataclass

__all__ = ["ActionPolicy", "Allow", "Deny", "Accept", "Reject", "Stop"]

_ANSWERS = ("accept", "reject")
_WHEN = ("always", "saving")


@dataclass(frozen=True)
class Allow:
    pass


@dataclass(frozen=True)
class Deny:
    reason: str


@dataclass(frozen=True)
class Accept:
    pass


@dataclass(frozen=True)
class Reject:
    pass


@dataclass(frozen=True)
class Stop:
    reason: str


def _contains_word(text, words):
    lowered = text.lower()
    return next((w for w in words if w in lowered), None)


class ActionPolicy:
    def __init__(self):
        self._screens = set()
        self._popups = {}
        self._calls = {}
        self._save_calls = set()
        self._forbidden = []
        self._dialogs = []

    def load(self, rules):
        screens = set(rules.get("screens", []))
        popups = {
            name: {"parent": spec["parent"], "opener": spec["opener"]}
            for name, spec in rules.get("popups", {}).items()
        }
        calls = {screen: set(fns) for screen, fns in rules.get("calls", {}).items()}
        save_calls = set(rules.get("save_calls", []))
        forbidden = [w.lower() for w in rules.get("forbidden", []) if w]
        dialogs = [self._compile_dialog(d) for d in rules.get("dialogs", [])]

        listed = set().union(*calls.values()) if calls else set()
        for fn in sorted(save_calls - listed):
            raise ValueError(f"save call {fn!r} is not in calls")
        names = listed | save_calls | {p["opener"] for p in popups.values()}
        for fn in sorted(names):
            word = _contains_word(fn, forbidden)
            if word:
                raise ValueError(f"function name {fn!r} contains forbidden word {word!r}")

        self._screens = screens
        self._popups = popups
        self._calls = calls
        self._save_calls = save_calls
        self._forbidden = forbidden
        self._dialogs = dialogs

    @staticmethod
    def _compile_dialog(rule):
        answer = rule["answer"]
        when = rule.get("when", "always")
        if answer not in _ANSWERS:
            raise ValueError(f"dialog answer must be one of {_ANSWERS}, got {answer!r}")
        if when not in _WHEN:
            raise ValueError(f"dialog when must be one of {_WHEN}, got {when!r}")
        try:
            regex = re.compile(rule["pattern"])
        except re.error as error:
            raise ValueError(f"bad dialog pattern {rule['pattern']!r}: {error}") from error
        return {
            "pattern": rule["pattern"],
            "regex": regex,
            "answer": answer,
            "when": when,
            "during": rule.get("during"),
        }

    def check_screen(self, screen, parent=None, opener=None):
        popup = self._popups.get(screen)
        if popup is not None:
            if parent == popup["parent"] and opener == popup["opener"]:
                return Allow()
            return Deny(
                f"popup {screen!r} may only be opened from {popup['parent']!r} by {popup['opener']!r}"
            )
        if screen in self._screens:
            return Allow()
        return Deny(f"screen {screen!r} is not allowed")

    def check_call(self, screen, fn, allow_save, saving):
        if screen not in self._screens and screen not in self._popups:
            return Deny(f"screen {screen!r} is not allowed")
        if fn not in self._calls.get(screen, ()):
            return Deny(f"function {fn!r} is not allowed on {screen!r}")
        word = _contains_word(fn, self._forbidden)
        if word:
            return Deny(f"function {fn!r} contains forbidden word {word!r}")
        if fn in self._save_calls and not (allow_save and saving):
            if not allow_save:
                return Deny(f"saving is not permitted for this job: {fn!r}")
            return Deny(f"{fn!r} writes and is only allowed in the save step")
        return Allow()

    def classify_dialog(self, text, saving, during=None):
        stripped = text.strip()
        if stripped.endswith("?") and _contains_word(stripped, self._forbidden):
            return Reject()
        answers = {
            rule["answer"]
            for rule in self._dialogs
            if rule["regex"].fullmatch(stripped)
            and (rule["when"] == "always" or saving)
            and (rule["during"] is None or rule["during"] == during)
        }
        if "reject" in answers:
            return Reject()
        if "accept" in answers:
            return Accept()
        return Stop(f"no rule for dialog {text!r}")

    def rules(self):
        return copy.deepcopy(
            {
                "screens": sorted(self._screens),
                "popups": self._popups,
                "calls": {screen: sorted(fns) for screen, fns in self._calls.items()},
                "save_calls": sorted(self._save_calls),
                "forbidden": sorted(self._forbidden),
                "dialogs": [
                    {k: v for k, v in rule.items() if k != "regex" and v is not None}
                    for rule in self._dialogs
                ],
            }
        )
