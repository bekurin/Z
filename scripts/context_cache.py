#!/usr/bin/env python3
"""Per-project context cache for the Clarity Gate.

Brownfield scoring reads target source files to assess the `context` dimension. Re-reading
the same unchanged files on every `z gate` run wastes context tokens. This cache stores a
short summary per file, keyed by the file's **content sha256**, so a later run can reuse the
summary instead of re-reading the whole file — and a changed file's hash no longer matches,
so it is transparently re-read.

The cache is **advisory** and **honest**: a HIT only ever returns a summary that was captured
from that exact file content. Change the bytes and the entry goes stale (MISS). It never
invents clarity the model did not actually read.

Storage: `<root>/.z/context/index.json` (root defaults to cwd; `.z/` is git-ignored).
Standard library only.

Usage:
    context_cache.py get   <path> [--root DIR]     # HIT: print summary / MISS
    context_cache.py put   <path> [--root DIR]     # summary read from stdin
    context_cache.py list        [--root DIR]
    context_cache.py prune       [--root DIR]
    context_cache.py clear       [--root DIR]

Exit codes:
    0  ok / cache HIT
    2  usage error
    3  cache MISS (get only)
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

CACHE_VERSION = 1
MISS = "MISS"


def _cache_file(root: Path) -> Path:
    return root / ".z" / "context" / "index.json"


def _load(root: Path) -> dict:
    """Load the index, tolerating a missing or malformed file (treated as empty)."""
    path = _cache_file(root)
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {"version": CACHE_VERSION, "entries": {}}
    if not isinstance(data, dict) or not isinstance(data.get("entries"), dict):
        return {"version": CACHE_VERSION, "entries": {}}
    data.setdefault("version", CACHE_VERSION)
    return data


def _save(root: Path, data: dict) -> None:
    """Atomically write the index (temp file + os.replace)."""
    path = _cache_file(root)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    os.replace(tmp, path)


def _rel_key(root: Path, path_str: str) -> str:
    """Stable, project-relative key for a file path (portable within the project)."""
    p = Path(path_str)
    if not p.is_absolute():
        p = root / p
    p = p.resolve()
    try:
        return p.relative_to(root).as_posix()
    except ValueError:
        # Outside the root — fall back to an absolute posix key.
        return p.as_posix()


def _file_sha256(root: Path, key: str) -> str | None:
    """sha256 of the file's bytes, or None if it cannot be read."""
    p = Path(key)
    if not p.is_absolute():
        p = root / p
    try:
        return hashlib.sha256(p.read_bytes()).hexdigest()
    except OSError:
        return None


def cmd_get(root: Path, path_str: str) -> int:
    entries = _load(root)["entries"]
    key = _rel_key(root, path_str)
    entry = entries.get(key)
    if not entry:
        print(MISS)
        return 3
    if _file_sha256(root, key) != entry.get("sha256"):
        print(MISS)
        return 3
    print(entry.get("summary", ""))
    return 0


def cmd_put(root: Path, path_str: str) -> int:
    key = _rel_key(root, path_str)
    digest = _file_sha256(root, key)
    if digest is None:
        print(f"error: cannot read file for {path_str!r}", file=sys.stderr)
        return 2
    summary = sys.stdin.read() if not sys.stdin.isatty() else ""
    summary = summary.strip("\n")
    data = _load(root)
    p = Path(key)
    size = (root / p if not p.is_absolute() else p).stat().st_size
    data["entries"][key] = {
        "sha256": digest,
        "summary": summary,
        "size": size,
        "updated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    }
    _save(root, data)
    return 0


def _freshness(root: Path, key: str, entry: dict) -> str:
    digest = _file_sha256(root, key)
    if digest is None:
        return "missing"
    return "fresh" if digest == entry.get("sha256") else "stale"


def cmd_list(root: Path) -> int:
    entries = _load(root)["entries"]
    if not entries:
        print("(empty)")
        return 0
    for key in sorted(entries):
        print(f"{_freshness(root, key, entries[key]):>7}  {key}")
    return 0


def cmd_prune(root: Path) -> int:
    data = _load(root)
    entries = data["entries"]
    dropped = [k for k, e in entries.items() if _freshness(root, k, e) != "fresh"]
    for k in dropped:
        del entries[k]
    _save(root, data)
    print(f"pruned {len(dropped)} stale/missing entr{'y' if len(dropped) == 1 else 'ies'}")
    return 0


def cmd_clear(root: Path) -> int:
    path = _cache_file(root)
    try:
        path.unlink()
    except FileNotFoundError:
        pass
    print("cleared")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="context_cache.py", description=__doc__)
    parser.add_argument("--root", default=".", help="project root holding .z/ (default: cwd)")
    sub = parser.add_subparsers(dest="command", required=True)
    for name in ("get", "put"):
        sp = sub.add_parser(name)
        sp.add_argument("path")
    for name in ("list", "prune", "clear"):
        sub.add_parser(name)
    return parser


def main(argv: list[str]) -> int:
    args = build_parser().parse_args(argv)
    root = Path(args.root).resolve()
    if args.command == "get":
        return cmd_get(root, args.path)
    if args.command == "put":
        return cmd_put(root, args.path)
    if args.command == "list":
        return cmd_list(root)
    if args.command == "prune":
        return cmd_prune(root)
    if args.command == "clear":
        return cmd_clear(root)
    return 2


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
