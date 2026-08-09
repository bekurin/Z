#!/usr/bin/env python3
"""Durable design-knowledge store for the Clarity Gate.

Unlike the per-file context cache (mechanical, content-hash keyed, auto-invalidating), this
manages cross-task design decisions and conventions the human curates — e.g. `api-design`,
`cache-key-design`.

Knowledge resolves in two layers so shared company standards are not copy-pasted per repo:

    org      a shared local directory of notes, configured per repo in .z/config.json
             ("knowledge_source"). Company-wide conventions, treated as read-only + static
             here (change them in the company knowledge repo).
    project  <root>/.z/knowledge/<topic>.md. Repo-specific notes; a project note of the same
             topic OVERRIDES the org note (specific > general).

Notes are plain markdown the human owns, with light frontmatter:

    ---
    topic: cache-key-design
    status: accepted            # proposed | accepted | superseded
    related_files:              # optional; project-layer only, drives advisory staleness
      - "src/**/cache/**"
    updated_at: 2026-08-06
    ---

Staleness is advisory and applies to project notes only: when a note's `related_files`
change, `check` flags it `review` (never deletes), and `touch` re-baselines. Org notes are
repo-agnostic conventions, so they are always reported `static`. Standard library only.

Usage:
    knowledge.py list                      [--root DIR]
    knowledge.py check  <topic>            [--root DIR]
    knowledge.py path   <topic>            [--root DIR]   # resolved file (project over org)
    knowledge.py touch  <topic>           [--root DIR]   # accept current project note state
    knowledge.py new    <topic>           [--root DIR]   # scaffold a project note
    knowledge.py config [--source DIR]    [--root DIR]   # show or set the org source

Exit codes:
    0  ok / fresh / static
    2  usage error (unknown topic, org note is read-only, note exists, …)
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


# ---- paths / config --------------------------------------------------------------

def _kdir(root: Path) -> Path:
    return root / ".z" / "knowledge"


def _index_path(root: Path) -> Path:
    return _kdir(root) / "index.json"


def _config_path(root: Path) -> Path:
    return root / ".z" / "config.json"


def _write_json(path: Path, data: dict) -> None:
    """Atomically write JSON (temp file + replace)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    tmp.replace(path)


def _load_json(path: Path) -> dict:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return data if isinstance(data, dict) else {}


def _load_config(root: Path) -> dict:
    return _load_json(_config_path(root))


def _org_dir(root: Path) -> Path | None:
    """Resolved org knowledge directory from .z/config.json, or None if not configured."""
    src = _load_config(root).get("knowledge_source")
    if not src:
        return None
    p = Path(src)
    return p if p.is_absolute() else root / p


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


# ---- note discovery / resolution -------------------------------------------------

def _notes_in_dir(directory: Path | None) -> dict[str, Path]:
    if not directory or not directory.is_dir():
        return {}
    return {p.stem: p for p in sorted(directory.glob("*.md")) if not p.name.startswith("_")}


def _project_notes(root: Path) -> dict[str, Path]:
    return _notes_in_dir(_kdir(root))


def _org_notes(root: Path) -> dict[str, Path]:
    return _notes_in_dir(_org_dir(root))


def resolve(root: Path) -> dict[str, dict]:
    """Merge org + project notes; project overrides org for the same topic."""
    org = _org_notes(root)
    result: dict[str, dict] = {
        t: {"topic": t, "path": p, "origin": "org", "shadows_org": False}
        for t, p in org.items()
    }
    for t, p in _project_notes(root).items():
        result[t] = {"topic": t, "path": p, "origin": "project", "shadows_org": t in org}
    return result


# ---- staleness (project notes only) ----------------------------------------------

def _file_hashes(root: Path, globs: list[str]) -> dict[str, str]:
    result: dict[str, str] = {}
    for pattern in globs:
        for p in root.glob(pattern):
            if p.is_file():
                result[p.relative_to(root).as_posix()] = hashlib.sha256(p.read_bytes()).hexdigest()
    return dict(sorted(result.items()))


def _diff(baseline: dict, current: dict) -> tuple[list[str], list[str], list[str]]:
    added = [k for k in current if k not in baseline]
    removed = [k for k in baseline if k not in current]
    changed = [k for k in current if k in baseline and current[k] != baseline[k]]
    return sorted(added), sorted(removed), sorted(changed)


def _status_of(root: Path, entry: dict, index: dict) -> tuple[str, dict]:
    """Return (status, detail). Org notes are always `static`; project notes use related_files."""
    if entry["origin"] == "org":
        return "static", {}
    meta = read_frontmatter(entry["path"].read_text(encoding="utf-8"))
    globs = meta.get("related_files") or []
    if not globs:
        return "static", {}
    current = _file_hashes(root, globs)
    base = index.get(entry["topic"])
    if not base or "files" not in base:
        return "unreviewed", {"current": current}
    added, removed, changed = _diff(base["files"], current)
    if not (added or removed or changed):
        return "fresh", {}
    return "review", {"added": added, "removed": removed, "changed": changed}


# ---- commands --------------------------------------------------------------------

def cmd_list(root: Path) -> int:
    resolved = resolve(root)
    if not resolved:
        print("(no knowledge notes)")
        return 0
    index = _load_index(root)
    for topic in sorted(resolved):
        entry = resolved[topic]
        status, _ = _status_of(root, entry, index)
        suffix = "  (overrides org)" if entry["shadows_org"] else ""
        print(f"{status:>10}  {entry['origin']:<7} {topic}{suffix}")
    return 0


def cmd_check(root: Path, topic: str) -> int:
    resolved = resolve(root)
    if topic not in resolved:
        print(f"error: no knowledge note for {topic!r}", file=sys.stderr)
        return 2
    entry = resolved[topic]
    status, detail = _status_of(root, entry, _load_index(root))
    origin = entry["origin"] + (" (overrides org)" if entry["shadows_org"] else "")
    print(f"{topic}: {status} [{origin}]")
    if status == "review":
        for label in ("changed", "added", "removed"):
            for f in detail.get(label, []):
                print(f"  {label}: {f}")
        print(f"  → review the note; if still correct, run: knowledge.py touch {topic}")
        return 4
    if status == "unreviewed":
        print(f"  → no baseline yet; run: knowledge.py touch {topic}")
        return 4
    return 0


def cmd_path(root: Path, topic: str) -> int:
    resolved = resolve(root)
    if topic not in resolved:
        print(f"error: no knowledge note for {topic!r}", file=sys.stderr)
        return 2
    print(resolved[topic]["path"])
    return 0


def cmd_touch(root: Path, topic: str) -> int:
    project = _project_notes(root)
    if topic not in project:
        if topic in _org_notes(root):
            print(f"error: {topic!r} is an org note (read-only here); create a project "
                  f"override with: knowledge.py new {topic}", file=sys.stderr)
        else:
            print(f"error: no knowledge note for {topic!r}", file=sys.stderr)
        return 2
    meta = read_frontmatter(project[topic].read_text(encoding="utf-8"))
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
    note = _kdir(root) / f"{topic}.md"
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
    shadow = " (overrides the org note of the same topic)" if topic in _org_notes(root) else ""
    print(f"created {note.relative_to(root)}{shadow} — edit it, then: knowledge.py touch {topic}")
    return 0


def cmd_config(root: Path, source: str | None) -> int:
    cfg = _load_config(root)
    if source is not None:
        cfg["knowledge_source"] = source
        _write_json(_config_path(root), cfg)
        print(f"knowledge_source set to: {source}")
        return 0
    src = cfg.get("knowledge_source")
    if not src:
        print("knowledge_source: (not set)")
        return 0
    resolved = Path(src) if Path(src).is_absolute() else root / src
    state = "exists" if resolved.is_dir() else "MISSING"
    print(f"knowledge_source: {src}")
    print(f"resolved: {resolved} ({state})")
    return 0


def _load_index(root: Path) -> dict:
    return _load_json(_index_path(root))


def _save_index(root: Path, data: dict) -> None:
    _write_json(_index_path(root), data)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="knowledge.py", description=__doc__)
    parser.add_argument("--root", default=".", help="project root holding .z/ (default: cwd)")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("list")
    for name in ("check", "path", "touch", "new"):
        sp = sub.add_parser(name)
        sp.add_argument("topic")
    cfg = sub.add_parser("config")
    cfg.add_argument("--source", help="set the org knowledge directory for this repo")
    return parser


def main(argv: list[str]) -> int:
    args = build_parser().parse_args(argv)
    root = Path(args.root).resolve()
    if args.command == "list":
        return cmd_list(root)
    if args.command == "check":
        return cmd_check(root, args.topic)
    if args.command == "path":
        return cmd_path(root, args.topic)
    if args.command == "touch":
        return cmd_touch(root, args.topic)
    if args.command == "new":
        return cmd_new(root, args.topic)
    if args.command == "config":
        return cmd_config(root, args.source)
    return 2


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
