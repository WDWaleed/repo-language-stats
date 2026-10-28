"""Tests for byte counting, line counting, percentage calculations, and aggregation."""

import pytest
from repo_language_stats.counting import (
    AggregateStats,
    LanguageStats,
    RepoStats,
    StatsAccumulator,
    aggregate_stats,
    calculate_percentage,
    count_bytes,
    count_lines,
)


def test_byte_count_ascii():
    text = "hello world"
    assert count_bytes(text) == len(text)
    assert count_bytes(text.encode("ascii")) == len(text)


def test_byte_count_utf8_multibyte():
    # 'café' has 4 characters but 5 UTF-8 bytes (é is 2 bytes: \xc3\xa9)
    word = "café"
    assert count_bytes(word) == 5
    assert count_bytes(word.encode("utf-8")) == 5

    # Test invalid bytes sequence handled with errors='replace'
    invalid_bytes = b"\xff\xfe\xfd"
    assert count_bytes(invalid_bytes) > 0


def test_line_count_trailing_newline():
    assert count_lines("a\nb\n") == 2
    assert count_lines(b"a\nb\n") == 2


def test_line_count_no_trailing_newline():
    assert count_lines("a\nb") == 2
    assert count_lines(b"a\nb") == 2
    assert count_lines("single line") == 1


def test_line_count_empty():
    assert count_lines("") == 0
    assert count_lines(b"") == 0


def test_line_count_single_newline():
    assert count_lines("\n") == 1
    assert count_lines(b"\n") == 1


def test_percentage_normal():
    assert calculate_percentage(500, 1000) == 50.0
    assert calculate_percentage(1, 3, round_digits=2) == 33.33
    assert calculate_percentage(1, 3, round_digits=None) == pytest.approx(33.333333333333336)


def test_percentage_zero_total():
    assert calculate_percentage(0, 0) == 0.0
    assert calculate_percentage(100, 0) == 0.0
    assert calculate_percentage(100, -5) == 0.0


def test_language_stats_add():
    stats = LanguageStats(language="Python", total_bytes=100, total_lines=10, file_count=1)
    stats.add(bytes_count=200, lines_count=25, files_count=2)
    assert stats.total_bytes == 300
    assert stats.total_lines == 35
    assert stats.file_count == 3


def test_repo_stats_properties():
    repo = RepoStats(repo_name="my-repo")
    assert repo.total_bytes == 0
    assert repo.total_lines == 0
    assert repo.total_files == 0

    repo.languages["Python"] = LanguageStats("Python", 100, 10, 1)
    repo.languages["Rust"] = LanguageStats("Rust", 200, 20, 2)

    assert repo.total_bytes == 300
    assert repo.total_lines == 30
    assert repo.total_files == 3


def test_aggregation_multiple_languages():
    items = [
        LanguageStats("Python", 100, 10, 1),
        LanguageStats("Rust", 200, 20, 1),
        LanguageStats("Python", 150, 15, 2),
        LanguageStats("Rust", 50, 5, 1),
    ]
    aggregated = aggregate_stats(items)
    assert len(aggregated) == 2

    assert aggregated["Python"].total_bytes == 250
    assert aggregated["Python"].total_lines == 25
    assert aggregated["Python"].file_count == 3

    assert aggregated["Rust"].total_bytes == 250
    assert aggregated["Rust"].total_lines == 25
    assert aggregated["Rust"].file_count == 2


def test_stats_accumulator_full_workflow():
    acc = StatsAccumulator(username="octocat")

    # Repo 1
    acc.start_repo("repo-one")
    acc.add_file("Python", "print('hello')\n")
    acc.add_file("Python", "print('world')\n")
    acc.add_file("Rust", "fn main() {}\n")
    acc.finish_repo(skipped=False)

    # Adding stats directly to an already finished repo in per_repo
    acc.add_stats("Python", bytes_count=50, lines_count=5, files_count=1, repo_name="repo-one")

    # Repo 2 (skipped)
    acc.start_repo("repo-skipped")
    acc.finish_repo(skipped=True)

    # Calling finish_repo when no current repo exists
    acc.finish_repo(skipped=False)

    # Adding stats without any current repo or repo_name
    acc.add_stats("Go", bytes_count=120, lines_count=12, files_count=1)

    # Repo 3: start repo, and add stats referencing matching repo_name explicitly
    acc.start_repo("repo-current")
    acc.add_stats("Python", bytes_count=20, lines_count=2, files_count=1, repo_name="repo-current")
    # And add stats referencing a DIFFERENT repo name
    acc.add_stats("Ruby", bytes_count=80, lines_count=8, files_count=1, repo_name="repo-different")

    # Explicitly finish the active repo before calling finalize
    acc.finish_repo(skipped=False)

    res = acc.finalize()
    assert isinstance(res, AggregateStats)
    assert res.username == "octocat"
    assert res.repos_scanned >= 2
    assert res.repos_skipped == 1
    assert "Python" in res.aggregate
    assert "Rust" in res.aggregate
    assert "Go" in res.aggregate
    assert "Ruby" in res.aggregate
    assert res.total_bytes > 0
    assert res.total_lines > 0


def test_stats_accumulator_consecutive_start_repo():
    acc = StatsAccumulator(username="octocat")
    acc.start_repo("repo-a")
    acc.add_file("Python", "x = 1\n")
    # Starting a new repo without finish_repo should auto-finish the previous one
    acc.start_repo("repo-b")
    acc.add_file("Rust", "y = 2\n")
    # finalize() should auto-finish repo-b
    res = acc.finalize()
    assert res.repos_scanned == 2
    assert len(res.per_repo) == 2
    assert res.per_repo[0].repo_name == "repo-a"
    assert res.per_repo[1].repo_name == "repo-b"
