import os

import pytest

from demo import scenarios
from demo.scenarios import main

HEADERS = [
    "=== Scenario 1: Dry run",
    "=== Scenario 2: Save and verify",
    "=== Scenario 3: A dialog nobody knows",
    "=== Scenario 4: The ERP lies about saving",
    "=== Scenario 5: The bot tries a forbidden function",
    "=== Scenario 6: Adapter error, duplicate send, STOP",
    "=== Scenario 7: The bot dies right after pressing save",
    "=== Scenario 8: Change a saved document",
    "=== Scenario 9: A person changed the document first",
    "=== Scenario 10: The removal question names another item",
]


@pytest.fixture(autouse=True)
def save_flag_off(monkeypatch):
    monkeypatch.delenv("LEA_FLAG_SAVE", raising=False)


def test_main_returns_zero_and_prints_every_scenario(capsys):
    assert main() == 0
    out = capsys.readouterr().out
    for header in HEADERS:
        assert header in out
    assert "[FAIL]" not in out
    assert out.count("verdict:") == 10
    assert out.count("final job state:") == 10
    assert "=== Summary ===" in out
    assert out.rstrip().endswith("These are invented fakes; passing says nothing about a real system.")


def test_summary_table_has_the_final_states(capsys):
    main()
    rows = [line for line in capsys.readouterr().out.splitlines() if line.startswith("  ") and " | " in line]
    states = [row.split(" | ")[1].strip() for row in rows[1:]]
    assert states == ["done", "done", "needs_human", "needs_human", "needs_human", "failed", "done", "done", "needs_human", "needs_human"]


def test_output_is_deterministic_and_ascii(capsys):
    main()
    first = capsys.readouterr().out
    main()
    second = capsys.readouterr().out
    assert first == second
    first.encode("ascii")


def test_demo_leaves_the_flag_as_it_found_it(monkeypatch, capsys):
    monkeypatch.setenv("LEA_FLAG_SAVE", "1")
    main()
    assert os.environ["LEA_FLAG_SAVE"] == "1"
    monkeypatch.delenv("LEA_FLAG_SAVE")
    main()
    assert "LEA_FLAG_SAVE" not in os.environ


@pytest.mark.parametrize("scenario", scenarios.SCENARIOS, ids=lambda f: f.__name__)
def test_each_scenario_ends_in_the_state_it_is_meant_to(scenario, capsys):
    outcome = scenario()
    assert outcome.failures == []
    assert outcome.ok


def test_a_scenario_that_ends_in_the_wrong_state_makes_the_demo_fail(monkeypatch, capsys):
    def wrong():
        return scenarios.Outcome(1, "Wrong", "done", "needs_human", "-", [])

    monkeypatch.setattr(scenarios, "SCENARIOS", (wrong,))
    assert main() == 1
    assert "[FAIL]" in capsys.readouterr().out
