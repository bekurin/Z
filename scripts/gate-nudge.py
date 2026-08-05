#!/usr/bin/env python3
"""UserPromptSubmit hook: nudge toward `z gate` on build-intent prompts.

Advisory only. If the prompt looks like an implementation request and the project has no
spec card yet (no .z/spec-cards/*.json), print a short reminder to stdout so it becomes
context for the model. Never blocks: always exits 0. Standard library only.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

BUILD_INTENT = re.compile(
    r"\b(build|implement|create|add|write|develop|refactor|feature)\b"
    r"|(만들|구현|개발|추가|리팩)",
    re.IGNORECASE,
)


def main() -> int:
    raw = sys.stdin.read() if not sys.stdin.isatty() else ""
    prompt = ""
    cwd = "."
    try:
        data = json.loads(raw)
        prompt = str(data.get("prompt", ""))
        cwd = str(data.get("cwd") or data.get("workspace") or ".")
    except (json.JSONDecodeError, AttributeError):
        prompt = raw  # tolerate a plain-text prompt on stdin

    if not prompt.strip() or not BUILD_INTENT.search(prompt):
        return 0

    cards_dir = Path(cwd) / ".z" / "spec-cards"
    has_card = cards_dir.is_dir() and any(cards_dir.glob("*.json"))
    if has_card:
        return 0

    print(
        "[z] This looks like implementation work and no Clarity Gate spec card exists "
        'yet. Consider running `z gate "<goal>"` first to pin the spec down '
        "(ambiguity <= 0.2) before building."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
