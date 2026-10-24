"""How a job is typed into the fake viewer. Never emits the dangerous functions or popups."""
from __future__ import annotations

import re

from app.adapters.ports import Call, Open, Set, Step


_REMOVE_DIALOG = re.compile(r"Remove item (\S+) from this document\?")


class FakeRecipe:
    removal_fn = "remove_line"
    item_field = "edit.code"

    def steps(self, payload: dict) -> list[Step]:
        steps: list[Step] = [Open("QuoteScreen"), Call("new_form"), Set("header.ref", payload["job"])]
        for i, line in enumerate(payload["lines"]):
            steps.append(Set(f"line[{i}].code", line["code"]))
            steps.append(Set(f"line[{i}].qty", str(line["qty"])))
            if line.get("price") is not None:
                steps.append(Set(f"line[{i}].price", format(line["price"], "f")))
            steps.append(Call("fill_line"))
        if payload.get("save"):
            steps.append(Call("save_form", is_save=True))
        return steps

    def read_back_steps(self, job: str) -> list[Step]:
        return [Open("ListScreen"), Call("refresh_list")]

    def read_back_ref(self, job: str) -> str:
        return job

    def edit_steps(self, ref: str, ops: list[dict]) -> list[Step]:
        steps: list[Step] = [Open("EditScreen"), Set("header.ref", ref), Call("load_document")]
        for op in ops:
            steps.append(Set(self.item_field, op["code"]))
            if op["op"] == "remove":
                steps.append(Call(self.removal_fn))
            elif op["op"] == "qty":
                steps.append(Set("edit.qty", str(op["qty"])))
                steps.append(Call("set_line_qty"))
            elif op["op"] == "add":
                steps.append(Set("edit.qty", str(op["qty"])))
                if op.get("price") is not None:
                    steps.append(Set("edit.price", format(op["price"], "f")))
                steps.append(Call("add_line"))
            else:
                raise ValueError(f"unknown op {op['op']!r}")
        steps.append(Call("update_form", is_save=True))
        return steps

    def item_in_dialog(self, text: str) -> str | None:
        match = _REMOVE_DIALOG.fullmatch(text)
        return match.group(1) if match else None
