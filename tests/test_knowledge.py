"""Behavioural tests for the design-knowledge store (scripts/knowledge.py).

Runs the script as a subprocess in a throwaway project. Verifies the advisory-staleness
contract: related-file changes flag a note `review` (never delete it), and `touch`
re-baselines. Also covers the frontmatter parser directly.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

from conftest import SCRIPTS

KNOW = SCRIPTS / "knowledge.py"

sys.path.insert(0, str(SCRIPTS))
import knowledge  # noqa: E402


NOTE = """\
---
topic: cache-key-design
status: accepted
related_files:
  - "src/**/cache/**"
updated_at: 2026-08-06
---
# Cache key design
Decision: colon-delimited namespaced keys.
"""


def run(root: Path, *args) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(KNOW), "--root", str(root), *args],
        capture_output=True, text=True,
    )


@pytest.fixture
def project(tmp_path: Path):
    """Scratch project with one knowledge note and one related file."""
    cache_dir = tmp_path / "src" / "cache"
    cache_dir.mkdir(parents=True)
    (cache_dir / "Lru.java").write_text("class LruCache {}\n", encoding="utf-8")
    kdir = tmp_path / ".z" / "knowledge"
    kdir.mkdir(parents=True)
    (kdir / "cache-key-design.md").write_text(NOTE, encoding="utf-8")
    return tmp_path


# ---- frontmatter parser ----

def test_frontmatter_scalars_and_list():
    meta = knowledge.read_frontmatter(NOTE)
    assert meta["topic"] == "cache-key-design"
    assert meta["status"] == "accepted"
    assert meta["related_files"] == ["src/**/cache/**"]


def test_frontmatter_inline_list():
    meta = knowledge.read_frontmatter('---\nrelated_files: ["a", "b"]\n---\n')
    assert meta["related_files"] == ["a", "b"]


def test_frontmatter_absent():
    assert knowledge.read_frontmatter("# no frontmatter\n") == {}


# ---- lifecycle ----

def test_check_unreviewed_before_baseline(project):
    result = run(project, "check", "cache-key-design")
    assert result.returncode == 4
    assert "unreviewed" in result.stdout


def test_touch_then_fresh(project):
    assert run(project, "touch", "cache-key-design").returncode == 0
    result = run(project, "check", "cache-key-design")
    assert result.returncode == 0
    assert "fresh" in result.stdout


def test_changed_related_file_flags_review_not_delete(project):
    run(project, "touch", "cache-key-design")
    (project / "src" / "cache" / "Lru.java").write_text("class LruCache { int x; }\n", encoding="utf-8")
    result = run(project, "check", "cache-key-design")
    assert result.returncode == 4
    assert "review" in result.stdout
    assert "Lru.java" in result.stdout
    # the note itself is untouched (advisory, never deleted)
    assert (project / ".z" / "knowledge" / "cache-key-design.md").is_file()


def test_new_related_file_is_detected(project):
    run(project, "touch", "cache-key-design")
    (project / "src" / "cache" / "Ttl.java").write_text("class Ttl {}\n", encoding="utf-8")
    result = run(project, "check", "cache-key-design")
    assert result.returncode == 4
    assert "Ttl.java" in result.stdout


def test_touch_reaccepts_after_change(project):
    run(project, "touch", "cache-key-design")
    (project / "src" / "cache" / "Lru.java").write_text("mutated\n", encoding="utf-8")
    assert run(project, "check", "cache-key-design").returncode == 4
    run(project, "touch", "cache-key-design")
    assert run(project, "check", "cache-key-design").returncode == 0


def test_note_with_no_related_files_is_static(project):
    (project / ".z" / "knowledge" / "api-design.md").write_text(
        "---\ntopic: api-design\nstatus: proposed\nrelated_files: []\n---\n# API\n",
        encoding="utf-8",
    )
    assert run(project, "check", "api-design").returncode == 0
    assert "static" in run(project, "check", "api-design").stdout


def test_list_reports_each_topic(project):
    out = run(project, "list").stdout
    assert "cache-key-design" in out


def test_new_scaffolds_and_rejects_duplicate(project):
    created = run(project, "new", "rate-limit-design")
    assert created.returncode == 0
    note = project / ".z" / "knowledge" / "rate-limit-design.md"
    assert note.is_file()
    assert "topic: rate-limit-design" in note.read_text(encoding="utf-8")
    dup = run(project, "new", "rate-limit-design")
    assert dup.returncode == 2
    assert "already exists" in dup.stderr


def test_check_unknown_topic_is_usage_error(project):
    result = run(project, "check", "does-not-exist")
    assert result.returncode == 2
    assert "no knowledge note" in result.stderr


# ---- org layer (shared company knowledge) ----

ORG_NOTE = """\
---
topic: api-design
status: accepted
updated_at: 2026-08-06
---
# API design (org standard)
"""


@pytest.fixture
def org_dir(tmp_path: Path):
    """A shared company knowledge directory outside any project."""
    d = tmp_path / "company-knowledge"
    d.mkdir()
    (d / "api-design.md").write_text(ORG_NOTE, encoding="utf-8")
    return d


def test_config_not_set_by_default(project):
    result = run(project, "config")
    assert result.returncode == 0
    assert "(not set)" in result.stdout


def test_config_set_and_show(project, org_dir):
    assert run(project, "config", "--source", str(org_dir)).returncode == 0
    cfg = project / ".z" / "config.json"
    assert cfg.is_file()
    import json
    assert json.loads(cfg.read_text())["knowledge_source"] == str(org_dir)
    show = run(project, "config")
    assert "exists" in show.stdout


def test_org_note_listed_with_origin_and_is_static(project, org_dir):
    run(project, "config", "--source", str(org_dir))
    out = run(project, "list").stdout
    assert "org" in out and "api-design" in out
    check = run(project, "check", "api-design")
    assert check.returncode == 0
    assert "static" in check.stdout and "[org]" in check.stdout


def test_project_overrides_org_for_same_topic(project, org_dir):
    # add an org note for the same topic the project already defines
    (org_dir / "cache-key-design.md").write_text(
        "---\ntopic: cache-key-design\nstatus: accepted\nupdated_at: 2026-08-06\n---\n# org\n",
        encoding="utf-8",
    )
    run(project, "config", "--source", str(org_dir))
    out = run(project, "list").stdout
    assert "overrides org" in out
    resolved = run(project, "path", "cache-key-design").stdout.strip()
    assert resolved == str(project / ".z" / "knowledge" / "cache-key-design.md")


def test_path_resolves_org_note_when_no_project_note(project, org_dir):
    run(project, "config", "--source", str(org_dir))
    resolved = run(project, "path", "api-design").stdout.strip()
    assert resolved == str(org_dir / "api-design.md")


def test_org_note_is_read_only_for_touch(project, org_dir):
    run(project, "config", "--source", str(org_dir))
    result = run(project, "touch", "api-design")
    assert result.returncode == 2
    assert "read-only" in result.stderr


def test_missing_org_source_is_ignored(project):
    run(project, "config", "--source", "/nope/does/not/exist")
    # only the project note remains resolvable; no crash
    assert run(project, "list").returncode == 0
    assert run(project, "path", "api-design").returncode == 2
    assert run(project, "check", "cache-key-design").returncode in (0, 4)


def test_new_creates_project_override_of_org_note(project, org_dir):
    run(project, "config", "--source", str(org_dir))
    created = run(project, "new", "api-design")
    assert created.returncode == 0
    assert "overrides the org note" in created.stdout
    assert run(project, "path", "api-design").stdout.strip() == str(
        project / ".z" / "knowledge" / "api-design.md"
    )
