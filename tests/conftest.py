"""Shared pytest fixtures and helpers for the Z harness.

Puts `scripts/` on the import path so tests can import `card_lib` directly, and exposes a
`make_card` factory that produces a valid, correctly-hashed card for mutation-based tests.
"""
from __future__ import annotations

import copy
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = ROOT / "scripts"
FIXTURES = Path(__file__).resolve().parent / "fixtures"
SCHEMA = ROOT / "schemas" / "spec-card.schema.json"
VALIDATOR = SCRIPTS / "validate-card.py"

sys.path.insert(0, str(SCRIPTS))
import card_lib  # noqa: E402


@pytest.fixture(scope="session")
def lib():
    """The deterministic core under test."""
    return card_lib


@pytest.fixture(scope="session")
def schema() -> dict:
    return json.loads(SCHEMA.read_text(encoding="utf-8"))


def fixture_path(name: str) -> Path:
    """Absolute path to a named fixture card (without the .json suffix)."""
    return FIXTURES / f"{name}.json"


def load_fixture(name: str) -> dict:
    return json.loads(fixture_path(name).read_text(encoding="utf-8"))


@pytest.fixture
def make_card():
    """Factory returning a fresh, valid, correctly-hashed greenfield card.

    Pass keyword overrides to mutate top-level fields; the content_hash is always
    recomputed so the returned card is internally consistent unless a test corrupts it.
    """
    def _make(**overrides) -> dict:
        dims = {
            "goal": {"weight": 0.40, "clarity": 0.9},
            "constraint": {"weight": 0.30, "clarity": 0.8},
            "success": {"weight": 0.30, "clarity": 0.8},
        }
        card = {
            "id": card_lib.card_id("sample goal", datetime(2026, 8, 4, tzinfo=timezone.utc)),
            "parent_id": None,
            "mode": "greenfield",
            "goal": "A sample, sufficiently concrete goal.",
            "constraints": ["Some constraint"],
            "success_criteria": [
                {"id": "AC1", "statement": "It works.", "verify": "Run it and observe success."}
            ],
            "non_goals": ["Something out of scope"],
            "assumptions": [],
            "open_questions": [],
            "ambiguity": {
                "score": round(card_lib.recompute_ambiguity("greenfield", dims), 6),
                "threshold": 0.2,
                "forced": False,
                "dimensions": dims,
            },
            "created_at": "2026-08-04T00:00:00Z",
            "content_hash": "",
            "frozen": True,
        }
        card = copy.deepcopy(card)
        card.update(overrides)
        card["content_hash"] = card_lib.content_hash(card)
        return card

    return _make
