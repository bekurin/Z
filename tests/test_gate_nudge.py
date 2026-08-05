"""Behavioural tests for the UserPromptSubmit nudge hook (scripts/gate-nudge.py).

The hook is advisory: it prints a reminder only when a build-intent prompt arrives and the
project has no spec card yet, and it must never block (always exit 0).
"""
from __future__ import annotations

import json
import subprocess
import sys

import pytest

from conftest import SCRIPTS

NUDGE = SCRIPTS / "gate-nudge.py"
MARKER = "[z]"


def run(payload: dict) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(NUDGE)],
        input=json.dumps(payload), capture_output=True, text=True,
    )


def test_build_intent_without_card_nudges(tmp_path):
    result = run({"prompt": "implement a CSV export feature", "cwd": str(tmp_path)})
    assert result.returncode == 0
    assert MARKER in result.stdout


@pytest.mark.parametrize("prompt", ["구현해줘", "이 기능을 만들어줘"])
def test_korean_build_intent_nudges(tmp_path, prompt):
    result = run({"prompt": prompt, "cwd": str(tmp_path)})
    assert result.returncode == 0
    assert MARKER in result.stdout


def test_non_build_prompt_is_silent(tmp_path):
    result = run({"prompt": "what does this function return?", "cwd": str(tmp_path)})
    assert result.returncode == 0
    assert result.stdout.strip() == ""


def test_silent_when_a_card_already_exists(tmp_path):
    cards = tmp_path / ".z" / "spec-cards"
    cards.mkdir(parents=True)
    (cards / "some-card-20260804T000000Z.json").write_text("{}", encoding="utf-8")
    result = run({"prompt": "add a new endpoint", "cwd": str(tmp_path)})
    assert result.returncode == 0
    assert result.stdout.strip() == ""


def test_empty_prompt_is_silent(tmp_path):
    result = run({"prompt": "", "cwd": str(tmp_path)})
    assert result.returncode == 0
    assert result.stdout.strip() == ""


def test_malformed_stdin_never_crashes():
    result = subprocess.run(
        [sys.executable, str(NUDGE)],
        input="not json at all", capture_output=True, text=True,
    )
    assert result.returncode == 0
