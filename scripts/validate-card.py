#!/usr/bin/env python3
"""Validate a Clarity Gate spec card.

Checks structure, the ambiguity arithmetic, threshold/forced consistency, the success
criteria shape, and the content hash (proving the frozen card was not tampered with). All
scoring constants come from card_lib so this CLI can never disagree with the harness.

Usage:  python3 validate-card.py .z/spec-cards/<id>.json
Exit:   0 = valid, 1 = invalid, 2 = usage / read error
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import card_lib  # noqa: E402  (path set above so the script runs from anywhere)

REQUIRED = [
    "id", "parent_id", "mode", "goal", "constraints", "success_criteria",
    "non_goals", "assumptions", "open_questions", "ambiguity", "created_at",
    "content_hash", "frozen",
]


def check(card: dict) -> tuple[list[str], list[str]]:
    """Return (errors, warnings) for a loaded card dict."""
    errors: list[str] = []
    warnings: list[str] = []

    for field in REQUIRED:
        if field not in card:
            errors.append(f"missing required field: {field}")

    if card.get("frozen") is not True:
        errors.append("frozen must be true")

    card_id = card.get("id")
    if isinstance(card_id, str) and not card_lib.is_valid_id(card_id):
        errors.append(f"id {card_id!r} does not match <slug>-<UTC timestamp> pattern")

    mode = card.get("mode")
    if mode not in card_lib.WEIGHTS:
        errors.append(f"mode must be greenfield|brownfield, got {mode!r}")
        mode = None

    amb = card.get("ambiguity", {})
    dims = amb.get("dimensions", {})
    score = amb.get("score")

    if mode is not None:
        weights = card_lib.weights_for(mode)
        if set(dims) != set(weights):
            errors.append(
                f"dimensions {sorted(dims)} do not match {mode} keys {sorted(weights)}"
            )
        for name, weight in weights.items():
            stored_w = dims.get(name, {}).get("weight")
            if stored_w is not None and abs(stored_w - weight) > 1e-9:
                warnings.append(f"{name}.weight={stored_w} != canonical {weight}")
            clarity = dims.get(name, {}).get("clarity")
            if not isinstance(clarity, (int, float)) or isinstance(clarity, bool) \
                    or not 0 <= clarity <= 1:
                errors.append(f"{name}.clarity must be a number in [0,1], got {clarity!r}")
        recomputed = card_lib.recompute_ambiguity(mode, dims)
        if isinstance(score, (int, float)) and abs(recomputed - score) > card_lib.EPS:
            errors.append(
                f"ambiguity.score={score} != recomputed {recomputed:.6f} (1 - sum(w*c))"
            )

    if isinstance(score, (int, float)) and score > card_lib.THRESHOLD + card_lib.EPS \
            and not amb.get("forced"):
        errors.append(
            f"score {score} exceeds threshold {card_lib.THRESHOLD} but forced is not true"
        )

    criteria = card.get("success_criteria", [])
    if not criteria:
        errors.append("success_criteria must have at least one entry")
    for i, crit in enumerate(criteria):
        if not isinstance(crit, dict):
            errors.append(f"success_criteria[{i}] must be an object")
            continue
        for key in ("id", "statement", "verify"):
            if not crit.get(key):
                errors.append(f"success_criteria[{i}] missing {key}")

    stored_hash = card.get("content_hash", "")
    expected = card_lib.content_hash(card)
    if stored_hash != expected:
        errors.append(
            "content_hash mismatch (card was modified after freezing)\n"
            f"    stored:   {stored_hash}\n    expected: {expected}"
        )

    return errors, warnings


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print("usage: validate-card.py <card.json>", file=sys.stderr)
        return 2
    try:
        with open(argv[1], encoding="utf-8") as fh:
            card = json.load(fh)
    except (OSError, json.JSONDecodeError) as exc:
        print(f"cannot read card: {exc}", file=sys.stderr)
        return 2

    errors, warnings = check(card)

    for w in warnings:
        print(f"WARN  {w}")
    if errors:
        for e in errors:
            print(f"FAIL  {e}")
        print(f"\n✗ invalid: {card.get('id', argv[1])}")
        return 1
    print(
        f"✓ valid: {card.get('id')}  "
        f"(ambiguity={card.get('ambiguity', {}).get('score')}, mode={card.get('mode')})"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
