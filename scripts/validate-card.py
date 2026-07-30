#!/usr/bin/env python3
"""Validate a Clarity Gate spec card.

Checks structure, the ambiguity arithmetic, threshold/forced consistency, and the
content hash (proving the frozen card was not tampered with). Standard library only.

Usage:  python3 validate-card.py .z/spec-cards/<id>.json
Exit:   0 = valid, 1 = invalid, 2 = usage / read error
"""
from __future__ import annotations

import hashlib
import json
import sys

THRESHOLD = 0.20
EPS = 1e-6

# Must stay in sync with agents/clarity-interviewer.md and skills/gate/SKILL.md.
WEIGHTS = {
    "greenfield": {"goal": 0.40, "constraint": 0.30, "success": 0.30},
    "brownfield": {"goal": 0.34, "constraint": 0.26, "success": 0.26, "context": 0.14},
}

REQUIRED = [
    "id", "parent_id", "mode", "goal", "constraints", "success_criteria",
    "non_goals", "assumptions", "open_questions", "ambiguity", "created_at",
    "content_hash", "frozen",
]


def canonical(card: dict) -> str:
    """Canonical form used for hashing: content_hash blanked, keys sorted, compact."""
    tmp = dict(card)
    tmp["content_hash"] = ""
    return json.dumps(tmp, sort_keys=True, separators=(",", ":"))


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

    errors: list[str] = []
    warnings: list[str] = []

    for field in REQUIRED:
        if field not in card:
            errors.append(f"missing required field: {field}")

    if card.get("frozen") is not True:
        errors.append("frozen must be true")

    mode = card.get("mode")
    if mode not in WEIGHTS:
        errors.append(f"mode must be greenfield|brownfield, got {mode!r}")
        mode = None

    amb = card.get("ambiguity", {})
    dims = amb.get("dimensions", {})
    score = amb.get("score")

    if mode is not None:
        weights = WEIGHTS[mode]
        if set(dims) != set(weights):
            errors.append(
                f"dimensions {sorted(dims)} do not match {mode} keys {sorted(weights)}"
            )
        total = 0.0
        for name, weight in weights.items():
            dim = dims.get(name, {})
            stored_w = dim.get("weight")
            clarity = dim.get("clarity")
            if stored_w is not None and abs(stored_w - weight) > 1e-9:
                warnings.append(
                    f"{name}.weight={stored_w} != canonical {weight}"
                )
            if not isinstance(clarity, (int, float)) or not (0 <= clarity <= 1):
                errors.append(f"{name}.clarity must be a number in [0,1], got {clarity!r}")
                clarity = 0
            total += weight * clarity
        recomputed = 1 - total
        if isinstance(score, (int, float)) and abs(recomputed - score) > EPS:
            errors.append(
                f"ambiguity.score={score} != recomputed {recomputed:.6f} (1 - sum(w*c))"
            )

    if isinstance(score, (int, float)) and score > THRESHOLD + EPS and not amb.get("forced"):
        errors.append(
            f"score {score} exceeds threshold {THRESHOLD} but forced is not true"
        )

    criteria = card.get("success_criteria", [])
    if not criteria:
        errors.append("success_criteria must have at least one entry")
    for i, crit in enumerate(criteria):
        for key in ("id", "statement", "verify"):
            if not crit.get(key):
                errors.append(f"success_criteria[{i}] missing {key}")

    stored_hash = card.get("content_hash", "")
    expected = "sha256:" + hashlib.sha256(canonical(card).encode()).hexdigest()
    if stored_hash != expected:
        errors.append(
            f"content_hash mismatch (card was modified after freezing)\n"
            f"    stored:   {stored_hash}\n    expected: {expected}"
        )

    for w in warnings:
        print(f"WARN  {w}")
    if errors:
        for e in errors:
            print(f"FAIL  {e}")
        print(f"\n✗ invalid: {card.get('id', argv[1])}")
        return 1
    print(f"✓ valid: {card.get('id')}  (ambiguity={score}, mode={mode})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
