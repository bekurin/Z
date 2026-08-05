#!/usr/bin/env python3
"""Deterministic core for Clarity Gate spec cards.

Single source of truth for the scoring weights, threshold, ambiguity arithmetic, and the
content-hash canonicalization. `validate-card.py` and the pytest harness both import from
here so the contract can never drift between them. Standard library only.

The formula is the contract:

    ambiguity = 1 - sum(weight_i * clarity_i)     PASS  <=>  ambiguity <= 0.20

Greenfield scores three dimensions; brownfield adds `context` and renormalizes so the
weights still sum to 1.00.
"""
from __future__ import annotations

import hashlib
import json
import re
from typing import Mapping

THRESHOLD: float = 0.20
"""Ambiguity at or below this passes the gate."""

EPS: float = 1e-6
"""Tolerance for float comparisons of the ambiguity arithmetic."""

MAX_ROUNDS: int = 8
"""Interview rounds the gate will run before it must stop."""

# Canonical weights. Keep these numbers in sync with the markdown surface
# (agents/clarity-interviewer.md, skills/gate/SKILL.md, README.md); test_contract_sync.py
# fails the build if they drift. Brownfield renormalizes 0.40/0.30/0.30 + context so the
# set still sums to exactly 1.00.
WEIGHTS: dict[str, dict[str, float]] = {
    "greenfield": {"goal": 0.40, "constraint": 0.30, "success": 0.30},
    "brownfield": {"goal": 0.35, "constraint": 0.26, "success": 0.26, "context": 0.13},
}

MODES = tuple(WEIGHTS)

_SLUG_STRIP = re.compile(r"[^a-z0-9]+")
_ID_PATTERN = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*-[0-9]{8}T[0-9]{6}Z$")


def weights_for(mode: str) -> dict[str, float]:
    """Return the weight map for a mode, or raise ValueError for an unknown mode."""
    try:
        return WEIGHTS[mode]
    except KeyError:
        raise ValueError(f"unknown mode {mode!r}; expected one of {list(MODES)}") from None


def recompute_ambiguity(mode: str, dimensions: Mapping[str, Mapping[str, float]]) -> float:
    """Recompute `1 - sum(weight * clarity)` from a card's dimensions.

    Uses the canonical `WEIGHTS[mode]` rather than the per-dimension weights stored on the
    card, so a card that misreports its own weights cannot fake a passing score. Clarity is
    read from the card; a missing or out-of-range clarity is treated as 0 (maximally
    ambiguous) so malformed input never lowers the score.
    """
    weights = weights_for(mode)
    total = 0.0
    for name, weight in weights.items():
        clarity = dimensions.get(name, {}).get("clarity")
        if not isinstance(clarity, (int, float)) or isinstance(clarity, bool):
            clarity = 0.0
        elif not 0.0 <= clarity <= 1.0:
            clarity = 0.0
        total += weight * clarity
    return 1.0 - total


def passes(score: float, forced: bool = False) -> bool:
    """A card passes when its ambiguity is at/below threshold, or the human forced it."""
    return forced or score <= THRESHOLD + EPS


def canonical(card: Mapping) -> str:
    """Canonical JSON used for hashing: `content_hash` blanked, keys sorted, compact."""
    tmp = dict(card)
    tmp["content_hash"] = ""
    return json.dumps(tmp, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def content_hash(card: Mapping) -> str:
    """`"sha256:" + sha256(canonical(card))` — the value stored on a frozen card."""
    digest = hashlib.sha256(canonical(card).encode("utf-8")).hexdigest()
    return f"sha256:{digest}"


def slugify(goal: str) -> str:
    """Kebab-case slug of a goal, suitable as the leading segment of a card id."""
    slug = _SLUG_STRIP.sub("-", goal.strip().lower()).strip("-")
    return slug or "card"


def card_id(goal: str, when) -> str:
    """Build `<slug>-<UTC compact timestamp>`, e.g. add-csv-export-20260730T142210Z.

    `when` is a timezone-aware or naive UTC datetime.
    """
    stamp = when.strftime("%Y%m%dT%H%M%SZ")
    return f"{slugify(goal)}-{stamp}"


def is_valid_id(value: str) -> bool:
    """True if `value` matches the schema id pattern."""
    return bool(_ID_PATTERN.match(value))
