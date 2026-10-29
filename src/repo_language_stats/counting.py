"""Byte and line counting engine and metric aggregation."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Sequence


@dataclass
class LanguageStats:
    """Aggregate statistics for a single language."""

    language: str
    total_bytes: int = 0
    total_lines: int = 0
    file_count: int = 0

    def add(self, bytes_count: int, lines_count: int, files_count: int = 1) -> None:
        """Add metrics to this language's statistics."""
        self.total_bytes += bytes_count
        self.total_lines += lines_count
        self.file_count += files_count


@dataclass
class RepoStats:
    """Per-repository breakdown."""

    repo_name: str
    languages: dict[str, LanguageStats] = field(default_factory=dict)

    @property
    def total_bytes(self) -> int:
        """Total source bytes in this repository."""
        return sum(s.total_bytes for s in self.languages.values())

    @property
    def total_lines(self) -> int:
        """Total source lines in this repository."""
        return sum(s.total_lines for s in self.languages.values())

    @property
    def total_files(self) -> int:
        """Total file count in this repository."""
        return sum(s.file_count for s in self.languages.values())


@dataclass
class AggregateStats:
    """Top-level results across repositories."""

    username: str
    repos_scanned: int = 0
    repos_skipped: int = 0
    per_repo: list[RepoStats] = field(default_factory=list)
    aggregate: dict[str, LanguageStats] = field(default_factory=dict)
    total_bytes: int = 0
    total_lines: int = 0


def count_bytes(content: str | bytes) -> int:
    """Count source bytes for the given content.

    Content is decoded/encoded as UTF-8 with errors='replace'.
    """
    if isinstance(content, bytes):
        text = content.decode("utf-8", errors="replace")
    else:
        text = content
    return len(text.encode("utf-8"))


def count_lines(content: str | bytes) -> int:
    """Count source lines for the given content.

    Counts newline-separated lines. An empty input yields 0 lines.
    Content without a trailing newline still counts its final line.
    """
    if isinstance(content, bytes):
        text = content.decode("utf-8", errors="replace")
    else:
        text = content

    if not text:
        return 0

    lines = text.count("\n")
    if not text.endswith("\n"):
        lines += 1
    return lines


def calculate_percentage(
    part: int | float,
    total: int | float,
    round_digits: int | None = 1,
) -> float:
    """Calculate percentage (part / total * 100).

    Returns 0.0 if total is 0.
    """
    if total <= 0:
        return 0.0
    val = (part / total) * 100.0
    if round_digits is not None:
        return round(val, round_digits)
    return val


# Canonical language grouping mappings
LANGUAGE_GROUPINGS: dict[str, str] = {
    "TSX": "TypeScript",
    "Jupyter (Python)": "Python",
}


def normalize_language_grouping(language: str) -> str:
    """Normalize language name to target display group (e.g. TSX -> TypeScript, Jupyter (Python) -> Python)."""
    return LANGUAGE_GROUPINGS.get(language, language)


def aggregate_stats(stats_list: Sequence[LanguageStats]) -> dict[str, LanguageStats]:
    """Aggregate a sequence of LanguageStats into a dictionary keyed by language name."""
    result: dict[str, LanguageStats] = {}
    for item in stats_list:
        lang = normalize_language_grouping(item.language)
        if lang not in result:
            result[lang] = LanguageStats(
                language=lang,
                total_bytes=item.total_bytes,
                total_lines=item.total_lines,
                file_count=item.file_count,
            )
        else:
            result[lang].add(
                bytes_count=item.total_bytes,
                lines_count=item.total_lines,
                files_count=item.file_count,
            )
    return result


class StatsAccumulator:
    """Accumulates file statistics across repositories and computes aggregate results."""

    def __init__(self, username: str = "") -> None:
        self.username = username
        self.repos_scanned = 0
        self.repos_skipped = 0
        self.per_repo: list[RepoStats] = []
        self.aggregate: dict[str, LanguageStats] = {}
        self._current_repo: RepoStats | None = None

    def start_repo(self, repo_name: str) -> RepoStats:
        """Begin accumulating stats for a new repository."""
        if self._current_repo is not None:
            self.finish_repo(skipped=False)
        self._current_repo = RepoStats(repo_name=repo_name)
        return self._current_repo

    def add_file(
        self,
        language: str,
        content: str | bytes,
        repo_name: str | None = None,
    ) -> None:
        """Count bytes and lines for content and accumulate."""
        b = count_bytes(content)
        l = count_lines(content)
        self.add_stats(language, bytes_count=b, lines_count=l, files_count=1, repo_name=repo_name)

    def add_stats(
        self,
        language: str,
        bytes_count: int,
        lines_count: int,
        files_count: int = 1,
        repo_name: str | None = None,
    ) -> None:
        """Add pre-computed metrics to aggregate and per-repository breakdown."""
        target_language = normalize_language_grouping(language)

        # Add to aggregate
        if target_language not in self.aggregate:
            self.aggregate[target_language] = LanguageStats(language=target_language)
        self.aggregate[target_language].add(bytes_count, lines_count, files_count)

        # Target repo resolution
        target_repo: RepoStats | None = None
        if repo_name is not None:
            for r in self.per_repo:
                if r.repo_name == repo_name:
                    target_repo = r
                    break
            if target_repo is None and self._current_repo is not None:
                if self._current_repo.repo_name == repo_name:
                    target_repo = self._current_repo
            if target_repo is None:
                target_repo = self.start_repo(repo_name)
        elif self._current_repo is not None:
            target_repo = self._current_repo

        if target_repo is not None:
            if target_language not in target_repo.languages:
                target_repo.languages[target_language] = LanguageStats(language=target_language)
            target_repo.languages[target_language].add(bytes_count, lines_count, files_count)

    def finish_repo(self, skipped: bool = False) -> None:
        """Mark the current repository as completed or skipped."""
        if skipped:
            self.repos_skipped += 1
            self._current_repo = None
        else:
            if self._current_repo is not None:
                self.per_repo.append(self._current_repo)
                self.repos_scanned += 1
                self._current_repo = None

    def finalize(self) -> AggregateStats:
        """Finalize and return top-level AggregateStats."""
        if self._current_repo is not None:
            self.finish_repo(skipped=False)

        tot_bytes = sum(s.total_bytes for s in self.aggregate.values())
        tot_lines = sum(s.total_lines for s in self.aggregate.values())

        return AggregateStats(
            username=self.username,
            repos_scanned=self.repos_scanned,
            repos_skipped=self.repos_skipped,
            per_repo=self.per_repo,
            aggregate=self.aggregate,
            total_bytes=tot_bytes,
            total_lines=tot_lines,
        )

