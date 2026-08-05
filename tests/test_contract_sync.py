"""Contract-drift guard.

The old CLAUDE.md warned that the weights/threshold live in several files and must be kept
in sync by hand. This test makes that guarantee mechanical: the numbers in the markdown
surface must match card_lib (the single source of truth). If someone changes a weight in
one place and forgets the others, the build goes red.
"""
from __future__ import annotations

import pytest

from conftest import ROOT


def _tokens(weights: dict[str, float]) -> set[str]:
    return {f"{w:.2f}" for w in weights.values()}


DOCS = [
    ROOT / "skills" / "gate" / "SKILL.md",
    ROOT / "agents" / "clarity-interviewer.md",
    ROOT / "README.md",
]


@pytest.mark.parametrize("doc", DOCS, ids=lambda p: p.name)
def test_doc_states_greenfield_weights(lib, doc):
    text = doc.read_text(encoding="utf-8")
    for token in _tokens(lib.WEIGHTS["greenfield"]):
        assert token in text, f"{doc.name} is missing greenfield weight {token}"


@pytest.mark.parametrize("doc", DOCS, ids=lambda p: p.name)
def test_doc_states_threshold(lib, doc):
    text = doc.read_text(encoding="utf-8")
    assert f"{lib.THRESHOLD:.2f}" in text, f"{doc.name} is missing threshold {lib.THRESHOLD:.2f}"


def test_gate_skill_states_brownfield_weights(lib):
    text = (ROOT / "skills" / "gate" / "SKILL.md").read_text(encoding="utf-8")
    for token in _tokens(lib.WEIGHTS["brownfield"]):
        assert token in text, f"gate SKILL is missing brownfield weight {token}"


def test_max_rounds_documented(lib):
    text = (ROOT / "skills" / "gate" / "SKILL.md").read_text(encoding="utf-8")
    assert str(lib.MAX_ROUNDS) in text
