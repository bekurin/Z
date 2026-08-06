#!/usr/bin/env python3
"""Durable design-knowledge store for the Clarity Gate.

Unlike the per-file context cache (mechanical, content-hash keyed, auto-invalidating), this
manages **cross-task design decisions and conventions** the human curates — e.g.
`api-design`, `cache-key-design`. Notes are plain markdown the human owns, at
`<root>/.z/knowledge/<topic>.md`, with light frontmatter:

    ---
    topic: cache-key-design
    status: accepted            # proposed | accepted | superseded
    related_files:
      - "src/**/cache/**"
    updated_at: 2026-08-06
    ---

Staleness is **advisory**: when the `related_files` change, the note is flagged `review`
(never deleted), because a design decision outlives any single code edit. The human reviews
and re-baselines with `touch`. Standard library only.

Usage:
    knowledge.py list                 [--root DIR]
    knowledge.py check <topic>        [--root DIR]
    knowledge.py touch <topic>        [--root DIR]   # accept current state as reviewed
    knowledge.py new   <topic>        [--root DIR]   # scaffold from the template

Exit codes:
    0  ok / fresh
    2  usage error (unknown topic, note exists, …)
    4  review recommended (check only: related files changed since last baseline)
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import date, datetime, timezone
from pathlib import Path

TEMPLATE = Path(__file__).resolve().parents[1] / "templates" / "knowledge" / "_template.md"


def _kdir(root: Path) -> Path:
    return root / ".z" / "knowledge"


def _note_path(root: Path, topic: str) -> Path:
    return _kdir(root) / f"{topic}.md"


def _index_path(root: Path) -> Path:
    return _kdir(root) / "index.json"


# ---- frontmatter -----------------------------------------------------------------

def _unquote(v: str) -> str:
    v = v.strip()
    if len(v) >= 2 and v[0] == v[-1] and v[0] in "\"'":
        return v[1:-1]
    return v


def read_frontmatter(text: str) -> dict:
    """Minimal YAML-subset frontmatter parser: scalars and simple `- item` lists."""
    if not text.startswith("---"):
        return {}
    lines = text.splitlines()
    end = next((i for i in range(1, len(lines)) if lines[i].strip() == "---"), None)
    if end is None:
        return {}
    meta: dict = {}
    current_list_key = None
    for line in lines[1:end]:
        if not line.strip():
            continue
        indented = line[:1] in (" ", "\t")
        stripped = line.strip()
        if indented and stripped.startswith("-") and current_list_key:
            meta[current_list_key].append(_unquote(stripped[1:]))
            continue
        if ":" in line and not indented:
            key, _, val = line.partition(":")
            key, val = key.strip(), val.strip()
            if val == "":
                meta[key] = []
                current_list_key = key
            elif val.startswith("[") and val.endswith("]"):
                inner = val[1:-1].strip()
                meta[key] = [_unquote(x) for x in inner.split(",")] if inner else []
                current_list_key = None
            else:
                meta[key] = _unquote(val)
                current_list_key = None
    return meta


# ---- hashing related files -------------------------------------------------------

def _file_hashes(root: Path, globs: list[str]) -> dict[str, str]:
    """Map of {relative posix path: sha256} for every existing file matching the globs."""
    result: dict[str, str] = {}
    for pattern in globs:
        for p in root.glob(pattern):
            if p.is_file():
                rel = p.relative_to(root).as_posix()
                result[rel] = hashlib.sha256(p.read_bytes()).hexdigest()
    return dict(sorted(result.items()))


def _load_index(root: Path) -> dict:
    try:
        data = json.loads(_index_path(root).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return data if isinstance(data, dict) else {}


def _save_index(root: Path, data: dict) -> None:
    path = _index_path(root)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    tmp.replace(path)


def _topics(root: Path) -> list[str]:
    kdir = _kdir(root)
    if not kdir.is_dir():
        return []
    return sorted(p.stem for p in kdir.glob("*.md") if not p.name.startswith("_"))


def _diff(baseline: dict, current: dict) -> tuple[list[str], list[str], list[str]]:
    added = [k for k in current if k not in baseline]
    removed = [k for k in baseline if k not in current]
    changed = [k for k in current if k in baseline and current[k] != baseline[k]]
    return sorted(added), sorted(removed), sorted(changed)


def _status_of(root: Path, topic: str, index: dict) -> tuple[str, dict]:
    """Return (status, detail). status ∈ fresh | review | unreviewed | static."""
    note = _note_path(root, topic)
    if not note.is_file():
        return "missing", {}
    meta = read_frontmatter(note.read_text(encoding="utf-8"))
    globs = meta.get("related_files") or []
    if not globs:
        return "static", {}
    current = _file_hashes(root, globs)
    entry = index.get(topic)
    if not entry or "files" not in entry:
        return "unreviewed", {"current": current}
    added, removed, changed = _diff(entry["files"], current)
    if not (added or removed or changed):
        return "fresh", {}
    return "review", {"added": added, "removed": removed, "changed": changed,
                      "current": current}


# ---- commands --------------------------------------------------------------------

def cmd_list(root: Path) -> int:
    index = _load_index(root)
    topics = _topics(root)
    if not topics:
        print("(no knowledge notes)")
        return 0
    for topic in topics:
        status, _ = _status_of(root, topic, index)
        print(f"{status:>10}  {topic}")
    return 0


def cmd_check(root: Path, topic: str) -> int:
    if not _note_path(root, topic).is_file():
        print(f"error: no knowledge note for {topic!r}", file=sys.stderr)
        return 2
    status, detail = _status_of(root, topic, _load_index(root))
    print(f"{topic}: {status}")
    if status == "review":
        for label, key in (("changed", "changed"), ("added", "added"), ("removed", "removed")):
            for f in detail.get(key, []):
                print(f"  {label}: {f}")
        print(f"  → review the note; if still correct, run: knowledge.py touch {topic}")
        return 4
    if status == "unreviewed":
        print(f"  → no baseline yet; run: knowledge.py touch {topic}")
        return 4
    return 0


def cmd_touch(root: Path, topic: str) -> int:
    note = _note_path(root, topic)
    if not note.is_file():
        print(f"error: no knowledge note for {topic!r}", file=sys.stderr)
        return 2
    meta = read_frontmatter(note.read_text(encoding="utf-8"))
    globs = meta.get("related_files") or []
    index = _load_index(root)
    index[topic] = {
        "files": _file_hashes(root, globs),
        "checked_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    }
    _save_index(root, index)
    print(f"{topic}: baseline recorded ({len(index[topic]['files'])} file(s))")
    return 0


def cmd_new(root: Path, topic: str) -> int:
    note = _note_path(root, topic)
    if note.exists():
        print(f"error: {note.relative_to(root)} already exists", file=sys.stderr)
        return 2
    try:
        body = TEMPLATE.read_text(encoding="utf-8")
    except OSError:
        body = ("---\ntopic: TOPIC_SLUG\nstatus: proposed\nrelated_files: []\n"
                "updated_at: DATE\n---\n\n# TITLE\n")
    body = (body.replace("TOPIC_SLUG", topic)
                .replace("DATE", date.today().isoformat())
                .replace("TITLE", topic.replace("-", " ").title()))
    note.parent.mkdir(parents=True, exist_ok=True)
    note.write_text(body, encoding="utf-8")
    print(f"created {note.relative_to(root)} — edit it, then: knowledge.py touch {topic}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="knowledge.py", description=__doc__)
    parser.add_argument("--root", default=".", help="project root holding .z/ (default: cwd)")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("list")
    for name in ("check", "touch", "new"):
        sp = sub.add_parser(name)
        sp.add_argument("topic")
    return parser


def main(argv: list[str]) -> int:
    args = build_parser().parse_args(argv)
    root = Path(args.root).resolve()
    if args.command == "list":
        return cmd_list(root)
    if args.command == "check":
        return cmd_check(root, args.topic)
    if args.command == "touch":
        return cmd_touch(root, args.topic)
    if args.command == "new":
        return cmd_new(root, args.topic)
    return 2


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
