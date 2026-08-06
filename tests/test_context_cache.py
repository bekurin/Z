"""Behavioural tests for the context cache (scripts/context_cache.py).

Runs the script as a subprocess in a throwaway project (`tmp_path`) so the content-hash
freshness contract is exercised exactly the way the gate skill drives it.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from conftest import SCRIPTS

CACHE = SCRIPTS / "context_cache.py"


def run(root: Path, *args, stdin: str | None = None) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(CACHE), "--root", str(root), *args],
        input=stdin, capture_output=True, text=True,
    )


@pytest.fixture
def project(tmp_path: Path):
    """A scratch project with one source file; returns (root, relative_path)."""
    src = tmp_path / "src"
    src.mkdir()
    f = src / "Foo.java"
    f.write_text("class Foo { void bar() {} }\n", encoding="utf-8")
    return tmp_path, "src/Foo.java"


def test_get_miss_before_put(project):
    root, rel = project
    result = run(root, "get", rel)
    assert result.returncode == 3
    assert result.stdout.strip() == "MISS"


def test_put_then_get_hit(project):
    root, rel = project
    assert run(root, "put", rel, stdin="Foo: one method bar().").returncode == 0
    result = run(root, "get", rel)
    assert result.returncode == 0
    assert result.stdout.strip() == "Foo: one method bar()."


def test_changed_content_invalidates(project):
    root, rel = project
    run(root, "put", rel, stdin="cached summary")
    (root / rel).write_text("class Foo { void bar() { changed(); } }\n", encoding="utf-8")
    result = run(root, "get", rel)
    assert result.returncode == 3
    assert result.stdout.strip() == "MISS"


def test_deleted_file_is_miss(project):
    root, rel = project
    run(root, "put", rel, stdin="cached summary")
    (root / rel).unlink()
    result = run(root, "get", rel)
    assert result.returncode == 3


def test_unknown_path_is_miss(project):
    root, _ = project
    result = run(root, "get", "src/DoesNotExist.java")
    assert result.returncode == 3


def test_put_on_missing_file_is_usage_error(project):
    root, _ = project
    result = run(root, "put", "src/Ghost.java", stdin="x")
    assert result.returncode == 2
    assert "cannot read file" in result.stderr


def test_absolute_and_relative_paths_share_one_entry(project):
    root, rel = project
    run(root, "put", rel, stdin="via relative")
    result = run(root, "get", str(root / rel))
    assert result.returncode == 0
    assert result.stdout.strip() == "via relative"


def test_list_reports_freshness(project):
    root, rel = project
    assert run(root, "list").stdout.strip() == "(empty)"
    run(root, "put", rel, stdin="s")
    assert "fresh" in run(root, "list").stdout
    (root / rel).write_text("mutated\n", encoding="utf-8")
    assert "stale" in run(root, "list").stdout


def test_prune_drops_stale_and_missing(project):
    root, rel = project
    run(root, "put", rel, stdin="s")
    (root / rel).write_text("mutated\n", encoding="utf-8")
    result = run(root, "prune")
    assert result.returncode == 0
    assert "pruned 1" in result.stdout
    assert run(root, "list").stdout.strip() == "(empty)"


def test_clear_removes_index(project):
    root, rel = project
    run(root, "put", rel, stdin="s")
    assert (root / ".z" / "context" / "index.json").exists()
    assert run(root, "clear").returncode == 0
    assert not (root / ".z" / "context" / "index.json").exists()


def test_malformed_index_is_tolerated_then_rebuilt(project):
    root, rel = project
    cache_file = root / ".z" / "context" / "index.json"
    cache_file.parent.mkdir(parents=True)
    cache_file.write_text("{ this is not valid json", encoding="utf-8")
    # get treats a corrupt index as empty
    assert run(root, "get", rel).returncode == 3
    # put rebuilds a well-formed index
    assert run(root, "put", rel, stdin="rebuilt").returncode == 0
    data = json.loads(cache_file.read_text(encoding="utf-8"))
    assert data["entries"][rel]["summary"] == "rebuilt"


def test_cache_written_under_dot_z(project):
    root, rel = project
    run(root, "put", rel, stdin="s")
    assert (root / ".z" / "context" / "index.json").is_file()
