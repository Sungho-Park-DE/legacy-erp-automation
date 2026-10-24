"""A pretend legacy form viewer: screens, dialogs, a save message that can lie, fault injection.

Invented for this demo. Behaviour is listed in app/adapters/README.md ("Fake behaviour reference").
"""
from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass

from app.adapters.ports import Document

SCREENS = ("HomeScreen", "QuoteScreen", "ListScreen", "EditScreen")
POPUP = "ItemPicker"
FUNCTIONS = {
    "QuoteScreen": ("new_form", "fill_line", "open_picker", "save_form", "print_form", "delete_form", "finalize_form"),
    "ItemPicker": ("pick_item", "close_picker"),
    "ListScreen": ("refresh_list", "open_row"),
    "EditScreen": ("load_document", "remove_line", "set_line_qty", "add_line", "update_form", "delete_form", "finalize_form"),
    "HomeScreen": (),
}
DANGEROUS = ("print_form", "delete_form", "finalize_form")
SAVE_MODES = ("ok", "lie_not_saved", "lie_altered")
NUMBERING = ("bot", "erp")

DIALOG_SAVE = "Save this form?"
DIALOG_SAVED = "Saved."
DIALOG_LOADED = "Loading complete."
DIALOG_DELETE = "Delete this document?"
DIALOG_PRINT = "Print this form?"
DIALOG_FINALIZE = "Finalize and lock this quote?"
DIALOG_UPDATE = "Save changes to this document?"

PICKER_ITEM = "P-100"

_FIELD = re.compile(r"^(?:header\.ref|line\[(\d+)\]\.(code|qty|price))$")
EDIT_FIELDS = ("header.ref", "edit.code", "edit.qty", "edit.price")


class ViewerError(Exception):
    pass


class SimulatedCrash(BaseException):
    """Stands for the bot process dying right after a save went through.

    Deliberately not an Exception, so no `except Exception` in the bot can swallow it.
    """


@dataclass
class _Dialog:
    text: str
    on_answer: Callable[[bool], None] | None = None


class FakeErpViewer:
    def __init__(
        self,
        save_mode: str = "ok",
        fail_on: tuple[str, ...] = (),
        dialog_on: dict[str, str] | None = None,
        numbering: str = "bot",
        crash_after_save: bool = False,
        name_in_removal: str | None = None,
        extra_request: str | None = None,
    ):
        if save_mode not in SAVE_MODES:
            raise ValueError(f"unknown save_mode {save_mode!r}, expected one of {SAVE_MODES}")
        if numbering not in NUMBERING:
            raise ValueError(f"unknown numbering {numbering!r}, expected one of {NUMBERING}")
        self.numbering = numbering
        self.crash_after_save = crash_after_save
        self.name_in_removal = name_in_removal
        self.extra_request = extra_request
        self._next_number = 1
        self._requests: list[str] = []
        self._edit: dict | None = None
        self.save_mode = save_mode
        self.fail_on = frozenset(fail_on)
        self.dialog_on = dict(dialog_on or {})
        self.documents: dict[str, Document] = {}
        self.locked: set[str] = set()
        self.dangerous_calls: list[str] = []
        self.printed: list[str] = []
        self.reset_count = 0
        self.current_screen = "HomeScreen"
        self.calls_made: list[tuple[str, str]] = []
        self._dialogs: list[_Dialog] = []
        self._form: dict | None = None

    def open_screen(self, screen: str) -> None:
        self._no_dialog_pending()
        if screen not in SCREENS:
            raise ViewerError(f"unknown screen {screen!r}")
        if screen in self.fail_on:
            raise ViewerError(f"open_screen {screen} failed")
        if self.current_screen == POPUP:
            raise ViewerError("close the picker first")
        self.current_screen = screen
        if screen == "ListScreen":
            self._requests.append("list")
            self._raise(DIALOG_LOADED)
        if screen == "EditScreen":
            self._edit = {"values": {}, "ref": None, "lines": None}
        self._raise_injected(screen)

    def set_value(self, path: str, value: str) -> None:
        if self.current_screen == "EditScreen":
            if path not in EDIT_FIELDS:
                raise ViewerError(f"unknown field {path!r}")
            self._edit["values"][path] = value
            return
        if self.current_screen != "QuoteScreen":
            raise ViewerError("set_value works only on QuoteScreen and EditScreen")
        form = self._need_form()
        match = _FIELD.match(path)
        if match is None:
            raise ViewerError(f"unknown field {path!r}")
        if path == "header.ref":
            form["header"]["ref"] = value
        else:
            form["values"].setdefault(int(match.group(1)), {})[match.group(2)] = value

    def call(self, fn: str) -> None:
        self._no_dialog_pending()
        if fn in self.fail_on:
            raise ViewerError(f"{fn} failed")
        if fn not in FUNCTIONS.get(self.current_screen, ()):
            raise ViewerError(f"{fn} does not belong to {self.current_screen}")
        self.calls_made.append((self.current_screen, fn))
        if fn in DANGEROUS:
            self.dangerous_calls.append(fn)
        getattr(self, f"_fn_{fn}")()
        self._raise_injected(fn)

    def pending_dialog(self) -> str | None:
        return self._dialogs[0].text if self._dialogs else None

    def answer_dialog(self, accept: bool) -> None:
        if not self._dialogs:
            raise ViewerError("no dialog pending")
        dialog = self._dialogs.pop(0)
        if dialog.on_answer is not None:
            dialog.on_answer(accept)

    def read_back(self, ref: str) -> Document:
        if self.current_screen != "ListScreen":
            raise ViewerError("read_back works only on ListScreen")
        document = self.documents.get(ref)
        if document is None:
            return Document(header={"ref": ref}, lines=[])
        return Document(header=self._shown_header(ref), lines=[dict(line) for line in document.lines])

    def list_documents(self) -> list[Document]:
        if self.current_screen != "ListScreen":
            raise ViewerError("list_documents works only on ListScreen")
        return [Document(header=self._shown_header(ref), lines=[]) for ref in self.documents]

    def request_log(self) -> list[str]:
        return list(self._requests)

    def edit_by_person(self, ref: str, lines: list[dict]) -> None:
        """Test hook: a person changed the document's lines in the ERP."""
        document = self.documents[ref]
        self.documents[ref] = Document(header=dict(document.header), lines=[dict(line) for line in lines])

    def reset(self) -> None:
        self._dialogs.clear()
        self._form = None
        self._edit = None
        self.current_screen = "HomeScreen"
        self.reset_count += 1

    def _shown_header(self, ref: str) -> dict[str, str]:
        header = dict(self.documents[ref].header)
        if ref in self.locked:
            header["status"] = "locked"
        return header

    def _finish_save(self) -> None:
        if self.crash_after_save:
            raise SimulatedCrash("bot process died after the save")
        self._raise(DIALOG_SAVED)

    def _no_dialog_pending(self) -> None:
        if self._dialogs:
            raise ViewerError("dialog pending")

    def _raise(self, text: str, on_answer: Callable[[bool], None] | None = None) -> None:
        self._dialogs.append(_Dialog(text, on_answer))

    def _raise_injected(self, key: str) -> None:
        if key in self.dialog_on:
            self._raise(self.dialog_on[key])

    def _need_form(self) -> dict:
        if self._form is None:
            raise ViewerError("no form in progress")
        return self._form

    def _need_ref(self) -> str:
        if self.current_screen == "EditScreen":
            return self._need_loaded()
        ref = self._need_form()["header"].get("ref", "")
        if not ref:
            raise ViewerError("header.ref is empty")
        return ref

    def _fn_new_form(self) -> None:
        self._form = {"header": {}, "values": {}, "lines": []}

    def _fn_fill_line(self) -> None:
        form = self._need_form()
        index = len(form["lines"])
        values = form["values"].get(index, {})
        if "code" not in values or "qty" not in values:
            raise ViewerError(f"line[{index}] needs code and qty")
        try:
            qty = int(values["qty"])
        except ValueError:
            raise ViewerError(f"line[{index}].qty is not a whole number") from None
        form["lines"].append({"code": values["code"], "qty": qty, "price": values.get("price")})

    def _fn_open_picker(self) -> None:
        self._need_form()
        self.current_screen = POPUP

    def _fn_pick_item(self) -> None:
        form = self._need_form()
        form["values"].setdefault(len(form["lines"]), {})["code"] = PICKER_ITEM

    def _fn_close_picker(self) -> None:
        self.current_screen = "QuoteScreen"

    def _fn_save_form(self) -> None:
        ref = self._need_ref()
        if ref in self.locked:
            raise ViewerError("document is locked")
        form = self._form
        lines = [dict(line) for line in form["lines"]]

        def on_answer(accept: bool) -> None:
            if not accept:
                return
            if self.save_mode != "lie_not_saved":
                if self.save_mode == "lie_altered" and lines:
                    lines[0]["qty"] += 1
                if self.numbering == "erp":
                    stored = f"D-{self._next_number:04d}"
                    self._next_number += 1
                    header = {"ref": stored, "note": ref}
                else:
                    stored, header = ref, {"ref": ref}
                self.documents[stored] = Document(header=header, lines=lines)
                self._requests.append("save")
            self._finish_save()

        self._raise(DIALOG_SAVE, on_answer)

    def _fn_print_form(self) -> None:
        ref = self._need_ref()

        def on_answer(accept: bool) -> None:
            if accept:
                self.printed.append(ref)
                self._requests.append("print")

        self._raise(DIALOG_PRINT, on_answer)

    def _fn_delete_form(self) -> None:
        ref = self._need_ref()

        def on_answer(accept: bool) -> None:
            if accept:
                self.documents.pop(ref, None)
                self._requests.append("delete")

        self._raise(DIALOG_DELETE, on_answer)

    def _fn_finalize_form(self) -> None:
        ref = self._need_ref()

        def on_answer(accept: bool) -> None:
            if accept:
                self.locked.add(ref)
                self._requests.append("finalize")

        self._raise(DIALOG_FINALIZE, on_answer)

    def _fn_refresh_list(self) -> None:
        self._requests.append("list")
        self._raise(DIALOG_LOADED)

    def _fn_open_row(self) -> None:
        pass

    def _need_loaded(self) -> str:
        if self._edit is None or self._edit["ref"] is None:
            raise ViewerError("no document loaded")
        return self._edit["ref"]

    def _edit_value(self, path: str) -> str:
        value = self._edit["values"].get(path)
        if not value:
            raise ViewerError(f"{path} is empty")
        return value

    def _edit_qty(self) -> int:
        try:
            return int(self._edit_value("edit.qty"))
        except ValueError:
            raise ViewerError("edit.qty is not a whole number") from None

    def _working_line(self, code: str) -> dict:
        for line in self._edit["lines"]:
            if line["code"] == code:
                return line
        raise ViewerError(f"item {code!r} is not in this document")

    def _fn_load_document(self) -> None:
        ref = self._edit["values"].get("header.ref", "")
        if ref not in self.documents:
            raise ViewerError(f"no document {ref!r}")
        self._edit["ref"] = ref
        self._edit["lines"] = [dict(line) for line in self.documents[ref].lines]
        self._requests.append("load")

    def _fn_remove_line(self) -> None:
        self._need_loaded()
        code = self._edit_value("edit.code")
        self._working_line(code)
        lines = self._edit["lines"]

        def on_answer(accept: bool) -> None:
            if accept:
                lines[:] = [line for line in lines if line["code"] != code]

        self._raise(f"Remove item {self.name_in_removal or code} from this document?", on_answer)

    def _fn_set_line_qty(self) -> None:
        self._need_loaded()
        line = self._working_line(self._edit_value("edit.code"))
        line["qty"] = self._edit_qty()

    def _fn_add_line(self) -> None:
        self._need_loaded()
        code = self._edit_value("edit.code")
        if any(line["code"] == code for line in self._edit["lines"]):
            raise ViewerError(f"item {code!r} is already in this document")
        qty = self._edit_qty()
        self._edit["lines"].append({"code": code, "qty": qty, "price": self._edit["values"].get("edit.price") or None})

    def _fn_update_form(self) -> None:
        ref = self._need_loaded()
        if ref in self.locked:
            raise ViewerError("document is locked")
        lines = self._edit["lines"]

        def on_answer(accept: bool) -> None:
            if not accept:
                return
            header = dict(self.documents[ref].header) if ref in self.documents else {"ref": ref}
            self.documents[ref] = Document(header=header, lines=[dict(line) for line in lines])
            self._requests.append("update")
            if self.extra_request:
                self._requests.append(self.extra_request)
            self._finish_save()

        self._raise(DIALOG_UPDATE, on_answer)
