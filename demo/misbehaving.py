"""Demo-only parts that misbehave on purpose, to show that the policy and the queue hold."""
from __future__ import annotations

from app.adapters import FakeErpViewer, FakeRecipe
from app.adapters.ports import Call, Step


class RecipeThatPrints:
    """Types the quote like FakeRecipe, then tries a function nobody may call."""

    def __init__(self) -> None:
        self._inner = FakeRecipe()

    def steps(self, payload: dict) -> list[Step]:
        return self._inner.steps(payload) + [Call("print_form")]

    def read_back_steps(self, job: str) -> list[Step]:
        return self._inner.read_back_steps(job)

    def read_back_ref(self, job: str) -> str:
        return self._inner.read_back_ref(job)


class RecipeThatSavesAnyway:
    """Always ends with a save step, even when the job is a dry run."""

    def __init__(self) -> None:
        self._inner = FakeRecipe()

    def steps(self, payload: dict) -> list[Step]:
        steps = self._inner.steps({**payload, "save": False})
        return steps + [Call("save_form", is_save=True)]

    def read_back_steps(self, job: str) -> list[Step]:
        return self._inner.read_back_steps(job)

    def read_back_ref(self, job: str) -> str:
        return self._inner.read_back_ref(job)


class ViewerWithStopButton(FakeErpViewer):
    """An operator hits STOP while the job is running: the first call flips the queue's switch."""

    def __init__(self) -> None:
        super().__init__()
        self.queue = None

    def call(self, fn: str) -> None:
        if self.queue is not None:
            self.queue.stop()
        super().call(fn)
