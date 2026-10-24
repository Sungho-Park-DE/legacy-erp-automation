"""How a job is typed into the fake viewer. Never emits the dangerous functions or popups."""
from __future__ import annotations

from app.adapters.ports import Call, Open, Set, Step


class FakeRecipe:
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
