"""Unit tests for the local filesystem scanner."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from repo_language_stats.benchmark import BenchmarkCollector
from repo_language_stats.discovery import TreeFilterConfig
from repo_language_stats.local_scanner import local_scan, _walk_directory
from repo_language_stats.counting import AggregateStats


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _write(path: Path, content: str = "x = 1\n") -> None:
    """Write *content* to *path*, creating parent directories as needed."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _minimal_notebook(language: str = "python") -> str:
    """Return a minimal valid .ipynb string with one code cell."""
    return json.dumps({
        "nbformat": 4,
        "nbformat_minor": 5,
        "metadata": {
            "kernelspec": {
                "display_name": language.capitalize(),
                "language": language,
                "name": language,
            }
        },
        "cells": [
            {
                "cell_type": "code",
                "source": "print('hello')\n",
                "metadata": {},
                "outputs": [],
                "execution_count": None,
            }
        ],
    })


# ---------------------------------------------------------------------------
# _walk_directory
# ---------------------------------------------------------------------------

def test_walk_directory_returns_relative_posix_paths(tmp_path: Path) -> None:
    _write(tmp_path / "src" / "main.py")
    _write(tmp_path / "README.md")
    entries = _walk_directory(tmp_path)
    paths = {e.path for e in entries}
    assert "src/main.py" in paths
    assert "README.md" in paths


def test_walk_directory_skips_git_dir(tmp_path: Path) -> None:
    _write(tmp_path / ".git" / "config", content="[core]\n")
    _write(tmp_path / "app.py")
    entries = _walk_directory(tmp_path)
    paths = {e.path for e in entries}
    assert all(".git" not in p for p in paths), "entries inside .git/ must be excluded"
    assert "app.py" in paths


def test_walk_directory_all_entries_are_blob_type(tmp_path: Path) -> None:
    _write(tmp_path / "foo.py")
    _write(tmp_path / "bar.ts")
    entries = _walk_directory(tmp_path)
    assert all(e.type == "blob" for e in entries)


def test_walk_directory_empty_dir(tmp_path: Path) -> None:
    entries = _walk_directory(tmp_path)
    assert entries == []


# ---------------------------------------------------------------------------
# local_scan — basic happy path
# ---------------------------------------------------------------------------

def test_local_scan_counts_python(tmp_path: Path) -> None:
    _write(tmp_path / "hello.py", "print('hello')\nprint('world')\n")
    result = local_scan(tmp_path)
    assert isinstance(result, AggregateStats)
    assert "Python" in result.aggregate
    assert result.aggregate["Python"].total_bytes > 0
    assert result.aggregate["Python"].total_lines == 2


def test_local_scan_counts_multiple_languages(tmp_path: Path) -> None:
    _write(tmp_path / "app.py", "x = 1\n")
    _write(tmp_path / "index.ts", "const x: number = 1;\n")
    _write(tmp_path / "style.css", "body { margin: 0; }\n")
    result = local_scan(tmp_path)
    langs = set(result.aggregate.keys())
    assert "Python" in langs
    assert "TypeScript" in langs
    assert "CSS" in langs


def test_local_scan_repo_name_matches_directory(tmp_path: Path) -> None:
    named_dir = tmp_path / "my-project"
    named_dir.mkdir()
    _write(named_dir / "main.py")
    result = local_scan(named_dir)
    assert result.repos_scanned == 1
    assert result.per_repo[0].repo_name == "my-project"


def test_local_scan_empty_directory(tmp_path: Path) -> None:
    result = local_scan(tmp_path)
    assert result.repos_scanned == 1
    assert result.aggregate == {}
    assert result.total_bytes == 0
    assert result.total_lines == 0


def test_local_scan_aggregates_bytes_and_lines(tmp_path: Path) -> None:
    content = "a = 1\nb = 2\n"
    f1 = tmp_path / "one.py"
    f2 = tmp_path / "two.py"
    _write(f1, content)
    _write(f2, content)
    result = local_scan(tmp_path)
    py = result.aggregate["Python"]
    # Use actual on-disk byte sizes to stay correct on Windows (CRLF) and Unix (LF)
    expected_bytes = len(f1.read_bytes()) + len(f2.read_bytes())
    assert py.total_bytes == expected_bytes
    assert py.total_lines == 4
    assert py.file_count == 2


# ---------------------------------------------------------------------------
# local_scan — .git/ exclusion
# ---------------------------------------------------------------------------

def test_local_scan_ignores_git_directory(tmp_path: Path) -> None:
    _write(tmp_path / ".git" / "HEAD", "ref: refs/heads/main\n")
    _write(tmp_path / "app.py", "pass\n")
    result = local_scan(tmp_path)
    # Only app.py should be counted; .git/HEAD must not appear
    assert result.total_bytes > 0
    total_files = sum(ls.file_count for ls in result.aggregate.values())
    assert total_files == 1


# ---------------------------------------------------------------------------
# local_scan — vendored / generated / docs exclusions
# ---------------------------------------------------------------------------

def test_local_scan_excludes_vendored_by_default(tmp_path: Path) -> None:
    _write(tmp_path / "vendor" / "lib.js", "var x = 1;\n")
    _write(tmp_path / "app.py", "pass\n")
    result = local_scan(tmp_path)
    # vendor/lib.js is vendored — only app.py counted
    total_files = sum(ls.file_count for ls in result.aggregate.values())
    assert total_files == 1
    assert "Python" in result.aggregate


def test_local_scan_excludes_docs_by_default(tmp_path: Path) -> None:
    _write(tmp_path / "README.md", "# Hello\n")
    _write(tmp_path / "app.py", "pass\n")
    result = local_scan(tmp_path)
    # Markdown is docs — excluded by default
    assert "Markdown" not in result.aggregate
    assert "Python" in result.aggregate


def test_local_scan_includes_docs_when_flag_set(tmp_path: Path) -> None:
    _write(tmp_path / "README.md", "# Hello\n")
    cfg = TreeFilterConfig(include_docs=True)
    result = local_scan(tmp_path, filter_config=cfg)
    assert "Markdown" in result.aggregate


def test_local_scan_excludes_default_data_formats(tmp_path: Path) -> None:
    """JSON, YAML, TOML, CSV, SVG are excluded by default."""
    _write(tmp_path / "data.json", '{"key": "value"}\n')
    _write(tmp_path / "config.yaml", "key: value\n")
    _write(tmp_path / "app.py", "pass\n")
    result = local_scan(tmp_path)
    assert "JSON" not in result.aggregate
    assert "YAML" not in result.aggregate
    assert "Python" in result.aggregate


def test_local_scan_all_flag_includes_data_formats(tmp_path: Path) -> None:
    _write(tmp_path / "data.json", '{"key": "value"}\n')
    cfg = TreeFilterConfig(include_all=True)
    result = local_scan(tmp_path, filter_config=cfg)
    assert "JSON" in result.aggregate


def test_local_scan_custom_exclude_pattern(tmp_path: Path) -> None:
    _write(tmp_path / "tests" / "test_app.py", "def test(): pass\n")
    _write(tmp_path / "app.py", "pass\n")
    cfg = TreeFilterConfig(exclude_patterns=["tests/**"])
    result = local_scan(tmp_path, filter_config=cfg)
    py = result.aggregate.get("Python")
    assert py is not None
    assert py.file_count == 1  # only app.py; tests/test_app.py excluded


def test_local_scan_include_vendored_flag(tmp_path: Path) -> None:
    _write(tmp_path / "vendor" / "lib.js", "var x = 1;\n")
    cfg = TreeFilterConfig(include_vendored=True)
    result = local_scan(tmp_path, filter_config=cfg)
    assert "JavaScript" in result.aggregate


# ---------------------------------------------------------------------------
# local_scan — Jupyter notebooks
# ---------------------------------------------------------------------------

def test_local_scan_parses_notebook_as_python(tmp_path: Path) -> None:
    nb_content = _minimal_notebook("python")
    _write(tmp_path / "analysis.ipynb", nb_content)
    result = local_scan(tmp_path)
    # Python-kernel notebooks are grouped under Python
    assert "Python" in result.aggregate
    assert result.aggregate["Python"].file_count == 1


def test_local_scan_malformed_notebook_skipped_gracefully(tmp_path: Path) -> None:
    _write(tmp_path / "broken.ipynb", "not valid json {{{{")
    _write(tmp_path / "app.py", "pass\n")
    # Must not raise
    result = local_scan(tmp_path)
    # broken.ipynb is skipped; app.py is still counted
    assert "Python" in result.aggregate


def test_local_scan_ipynb_language_fallback(tmp_path: Path) -> None:
    nb = json.dumps({
        "nbformat": 4,
        "nbformat_minor": 5,
        "metadata": {},
        "cells": [{"cell_type": "code", "source": "x <- 1\n", "metadata": {}, "outputs": [], "execution_count": None}],
    })
    _write(tmp_path / "stats.ipynb", nb)
    result = local_scan(tmp_path, ipynb_language="R")
    # With no kernel metadata but ipynb_language="R", should fall under R or Jupyter (R)
    lang_keys = set(result.aggregate.keys())
    assert any("R" in k or "Jupyter" in k for k in lang_keys)


# ---------------------------------------------------------------------------
# local_scan — TSX → TypeScript grouping
# ---------------------------------------------------------------------------

def test_local_scan_tsx_grouped_under_typescript(tmp_path: Path) -> None:
    _write(tmp_path / "Button.tsx", "export const Button = () => <button />;\n")
    result = local_scan(tmp_path)
    assert "TypeScript" in result.aggregate
    assert "TSX" not in result.aggregate


# ---------------------------------------------------------------------------
# local_scan — error handling
# ---------------------------------------------------------------------------

def test_local_scan_raises_on_nonexistent_path() -> None:
    with pytest.raises(FileNotFoundError):
        local_scan("/nonexistent/path/that/does/not/exist")


def test_local_scan_raises_on_file_not_directory(tmp_path: Path) -> None:
    f = tmp_path / "file.py"
    f.write_text("pass\n")
    with pytest.raises(NotADirectoryError):
        local_scan(f)


# ---------------------------------------------------------------------------
# local_scan — benchmark integration
# ---------------------------------------------------------------------------

def test_local_scan_benchmark_cpu_times_nonzero(tmp_path: Path) -> None:
    for i in range(10):
        _write(tmp_path / f"module_{i}.py", f"# module {i}\nx = {i}\n")
    bm = BenchmarkCollector()
    local_scan(tmp_path, benchmark=bm)
    # CPU time must be recorded; network time must remain zero
    assert bm.total_cpu_time_s > 0.0
    assert bm.total_network_time_s == 0.0
    assert bm.files_processed > 0
    assert bm.lines_counted > 0


def test_local_scan_benchmark_repos_benchmarked(tmp_path: Path) -> None:
    _write(tmp_path / "app.py", "pass\n")
    bm = BenchmarkCollector()
    local_scan(tmp_path, benchmark=bm)
    assert bm.repos_benchmarked == 1


def test_local_scan_benchmark_source_bytes_recorded(tmp_path: Path) -> None:
    content = "print('hello world')\n"
    f = tmp_path / "hello.py"
    _write(f, content)
    bm = BenchmarkCollector()
    local_scan(tmp_path, benchmark=bm)
    # Use actual on-disk byte count to stay correct on Windows (CRLF) and Unix (LF)
    assert bm.source_bytes_counted == len(f.read_bytes())


def test_local_scan_no_benchmark_still_works(tmp_path: Path) -> None:
    _write(tmp_path / "app.py", "pass\n")
    result = local_scan(tmp_path, benchmark=None)
    assert "Python" in result.aggregate
