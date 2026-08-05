"""Unit tests for the deterministic core (scripts/card_lib.py).

These pin the contract math and hashing so any drift is caught before it reaches a card.
"""
from __future__ import annotations

from datetime import datetime, timezone

import pytest


def test_greenfield_weights_sum_to_one(lib):
    assert abs(sum(lib.WEIGHTS["greenfield"].values()) - 1.0) < 1e-9


def test_brownfield_weights_sum_to_one(lib):
    assert abs(sum(lib.WEIGHTS["brownfield"].values()) - 1.0) < 1e-9


def test_threshold_is_the_documented_contract(lib):
    assert lib.THRESHOLD == 0.20


@pytest.mark.parametrize(
    "mode,clarities,expected",
    [
        ("greenfield", {"goal": 1.0, "constraint": 1.0, "success": 1.0}, 0.0),
        ("greenfield", {"goal": 0.0, "constraint": 0.0, "success": 0.0}, 1.0),
        ("greenfield", {"goal": 0.9, "constraint": 0.8, "success": 0.8}, 0.16),
        ("brownfield", {"goal": 1.0, "constraint": 1.0, "success": 1.0, "context": 1.0}, 0.0),
    ],
)
def test_recompute_ambiguity_matches_formula(lib, mode, clarities, expected):
    dims = {k: {"clarity": v} for k, v in clarities.items()}
    assert abs(lib.recompute_ambiguity(mode, dims) - expected) < lib.EPS


def test_recompute_uses_canonical_weights_not_card_weights(lib):
    """A card that lies about its per-dimension weights cannot fake a better score."""
    dims = {
        "goal": {"weight": 0.99, "clarity": 1.0},
        "constraint": {"weight": 0.0, "clarity": 0.0},
        "success": {"weight": 0.0, "clarity": 0.0},
    }
    # If it honored the card's weights, score would be ~0.01; with canonical weights it's 0.6.
    assert abs(lib.recompute_ambiguity("greenfield", dims) - 0.6) < lib.EPS


@pytest.mark.parametrize("bad", [None, "0.9", True, -0.1, 1.5, {}])
def test_out_of_range_or_nonnumeric_clarity_counts_as_zero(lib, bad):
    dims = {"goal": {"clarity": bad}, "constraint": {"clarity": 1.0}, "success": {"clarity": 1.0}}
    # goal contributes 0, so ambiguity = 1 - (0 + 0.3 + 0.3) = 0.4
    assert abs(lib.recompute_ambiguity("greenfield", dims) - 0.4) < lib.EPS


def test_unknown_mode_raises(lib):
    with pytest.raises(ValueError):
        lib.recompute_ambiguity("legacy", {})


def test_passes_boundary(lib):
    assert lib.passes(0.20) is True
    assert lib.passes(0.20 + 1e-3) is False
    assert lib.passes(0.99, forced=True) is True


def test_canonical_blanks_hash_and_is_order_stable(lib, make_card):
    card = make_card()
    reordered = {k: card[k] for k in reversed(list(card))}
    assert lib.canonical(card) == lib.canonical(reordered)
    assert '"content_hash":""' in lib.canonical(card)


def test_content_hash_is_deterministic(lib, make_card):
    card = make_card()
    assert lib.content_hash(card) == lib.content_hash(dict(card))


def test_content_hash_changes_when_any_field_changes(lib, make_card):
    card = make_card()
    before = lib.content_hash(card)
    card["goal"] = card["goal"] + " (revised)"
    assert lib.content_hash(card) != before


def test_content_hash_independent_of_stored_hash_value(lib, make_card):
    """Blanking content_hash before hashing means the stored value can't affect the digest."""
    card = make_card()
    h = lib.content_hash(card)
    card["content_hash"] = "sha256:" + "0" * 64
    assert lib.content_hash(card) == h


def test_card_id_matches_schema_pattern(lib):
    cid = lib.card_id("Add CSV Export!", datetime(2026, 7, 30, 14, 22, 10, tzinfo=timezone.utc))
    assert cid == "add-csv-export-20260730T142210Z"
    assert lib.is_valid_id(cid)


def test_slugify_collapses_punctuation_and_never_empty(lib):
    assert lib.slugify("  Hello, World!!  ") == "hello-world"
    assert lib.slugify("###") == "card"
