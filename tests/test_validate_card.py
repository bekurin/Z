"""Behavioural tests for the validate-card.py CLI.

Runs the script as a subprocess (the way a user or a hook would) and asserts on exit codes
and the specific FAIL line, so each check is pinned to the fixture that should trigger it.
"""
from __future__ import annotations

import subprocess
import sys

import pytest

from conftest import VALIDATOR, fixture_path


def run(*args) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(VALIDATOR), *args],
        capture_output=True, text=True,
    )


@pytest.mark.parametrize("name", ["valid_greenfield", "valid_brownfield", "forced_pass"])
def test_valid_cards_exit_zero(name):
    result = run(str(fixture_path(name)))
    assert result.returncode == 0, result.stdout + result.stderr
    assert "✓ valid" in result.stdout


@pytest.mark.parametrize(
    "name,needle",
    [
        ("tampered_hash", "content_hash mismatch"),
        ("bad_math", "!= recomputed"),
        ("missing_field", "missing required field: non_goals"),
        ("bad_ac", "success_criteria[0] missing verify"),
    ],
)
def test_invalid_cards_exit_one_with_reason(name, needle):
    result = run(str(fixture_path(name)))
    assert result.returncode == 1, result.stdout + result.stderr
    assert needle in result.stdout


def test_missing_argument_is_usage_error():
    result = run()
    assert result.returncode == 2
    assert "usage" in result.stderr.lower()


def test_unreadable_file_is_usage_error():
    result = run("tests/fixtures/does-not-exist.json")
    assert result.returncode == 2
    assert "cannot read card" in result.stderr


def test_forced_flag_removed_makes_over_threshold_card_invalid(make_card, tmp_path):
    """A card over threshold without forced:true must fail the forced-consistency check."""
    dims = {
        "goal": {"weight": 0.40, "clarity": 0.3},
        "constraint": {"weight": 0.30, "clarity": 0.3},
        "success": {"weight": 0.30, "clarity": 0.3},
    }
    card = make_card()
    card["ambiguity"] = {"score": 0.7, "threshold": 0.2, "forced": False, "dimensions": dims}
    # rewrite the hash so ONLY the forced/threshold rule (and the math) can fail
    import json
    import card_lib
    card["content_hash"] = card_lib.content_hash(card)
    p = tmp_path / "over.json"
    p.write_text(json.dumps(card), encoding="utf-8")
    result = run(str(p))
    assert result.returncode == 1
    assert "exceeds threshold" in result.stdout
