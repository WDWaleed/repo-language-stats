"""File tree filtering and exclusion rules for repository scanning."""

from __future__ import annotations

from dataclasses import dataclass, field
from fnmatch import fnmatch
from pathlib import Path
import re
from typing import Any, Sequence
import yaml

from repo_language_stats.language import (
    classify,
    get_language_type,
    is_binary,
    is_notebook,
)


def _get_data_path(filename: str) -> Path:
    """Resolve path to vendored data file."""
    path = Path(__file__).resolve().parent / "data" / filename
    if path.exists():
        return path
    try:
        from importlib.resources import files

        return Path(str(files("repo_language_stats.data").joinpath(filename)))
    except Exception:
        return path


@dataclass
class TreeFilterConfig:
    """Configuration for filtering repository file trees."""

    include_generated: bool = False
    include_vendored: bool = False
    include_docs: bool = False
    exclude_patterns: list[str] = field(default_factory=list)


@dataclass
class TreeEntry:
    """An entry in a Git tree."""

    path: str
    mode: str = "100644"
    type: str = "blob"
    sha: str = ""
    size: int | None = None
    url: str = ""

    @classmethod
    def from_api_dict(cls, data: dict[str, Any]) -> TreeEntry:
        """Create a TreeEntry from a GitHub Git Trees API dictionary."""
        return cls(
            path=data.get("path", ""),
            mode=data.get("mode", "100644"),
            type=data.get("type", "blob"),
            sha=data.get("sha", ""),
            size=data.get("size"),
            url=data.get("url", ""),
        )


class FileDiscoveryFilter:
    """Filters repository tree entries according to Linguist and custom exclusion rules."""

    def __init__(
        self,
        vendor_file: Path | str | None = None,
        generated_file: Path | str | None = None,
    ) -> None:
        v_path = Path(vendor_file) if vendor_file else _get_data_path("vendor.yml")
        g_path = Path(generated_file) if generated_file else _get_data_path("generated_patterns.txt")

        self._vendor_regexes: list[re.Pattern[str]] = []
        self._generated_regexes: list[re.Pattern[str]] = []

        self._load_vendor_patterns(v_path)
        self._load_generated_patterns(g_path)

    def _load_vendor_patterns(self, path: Path) -> None:
        """Load and compile vendor path regex patterns."""
        if not path.exists():
            return
        with open(path, "r", encoding="utf-8") as f:
            patterns = yaml.safe_load(f) or []
        for pat in patterns:
            try:
                self._vendor_regexes.append(re.compile(pat, re.IGNORECASE))
            except re.error:
                continue

    def _load_generated_patterns(self, path: Path) -> None:
        """Load and compile generated file regex patterns."""
        if not path.exists():
            return
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                try:
                    self._generated_regexes.append(re.compile(line, re.IGNORECASE))
                except re.error:
                    continue

    def is_vendored(self, path: str) -> bool:
        """Check if a path matches any vendored path patterns."""
        norm_path = path.replace("\\", "/")
        return any(rx.search(norm_path) for rx in self._vendor_regexes)

    def is_generated(self, path: str) -> bool:
        """Check if a path matches any generated file patterns."""
        norm_path = path.replace("\\", "/")
        filename = Path(norm_path).name
        # Check against full path or basename
        return any(rx.search(norm_path) or rx.search(filename) for rx in self._generated_regexes)

    def is_documentation(self, path: str) -> bool:
        """Check if a path is considered documentation/prose."""
        lang = classify(path)
        if lang:
            l_type = get_language_type(lang)
            if l_type == "prose":
                return True
        # Common doc extensions if not classified
        ext = Path(path).suffix.lower()
        return ext in {".md", ".rst", ".txt", ".adoc", ".asciidoc"}

    def is_eligible(
        self,
        path: str,
        config: TreeFilterConfig | None = None,
        entry_type: str = "blob",
    ) -> bool:
        """Determine if a file path is eligible for scanning under the given configuration."""
        # Only process blob entries
        if entry_type != "blob":
            return False

        # Binaries are always excluded
        if is_binary(path):
            return False

        cfg = config or TreeFilterConfig()

        # Check custom exclusion globs
        norm_path = path.replace("\\", "/")
        filename = Path(norm_path).name
        for pattern in cfg.exclude_patterns:
            if fnmatch(norm_path, pattern) or fnmatch(filename, pattern):
                return False

        # Check vendored
        if not cfg.include_vendored and self.is_vendored(norm_path):
            return False

        # Check generated
        if not cfg.include_generated and self.is_generated(norm_path):
            return False

        # Check documentation
        if not cfg.include_docs and self.is_documentation(norm_path):
            return False

        # File must be a recognizable language or notebook
        if is_notebook(norm_path):
            return True

        lang = classify(norm_path)
        return lang is not None

    def filter_tree(
        self,
        entries: Sequence[TreeEntry | dict[str, Any]],
        config: TreeFilterConfig | None = None,
    ) -> list[TreeEntry]:
        """Filter a collection of tree entries, returning only eligible files."""
        eligible_entries: list[TreeEntry] = []
        for entry in entries:
            if isinstance(entry, dict):
                tree_entry = TreeEntry.from_api_dict(entry)
            else:
                tree_entry = entry

            if self.is_eligible(
                path=tree_entry.path,
                config=config,
                entry_type=tree_entry.type,
            ):
                eligible_entries.append(tree_entry)

        return eligible_entries


# Global default filter instance
_DEFAULT_FILTER: FileDiscoveryFilter | None = None


def get_default_filter() -> FileDiscoveryFilter:
    """Get or create the global default FileDiscoveryFilter instance."""
    global _DEFAULT_FILTER
    if _DEFAULT_FILTER is None:
        _DEFAULT_FILTER = FileDiscoveryFilter()
    return _DEFAULT_FILTER


def is_eligible(
    path: str,
    config: TreeFilterConfig | None = None,
    entry_type: str = "blob",
) -> bool:
    """Check if a path is eligible using the default discovery filter."""
    return get_default_filter().is_eligible(path, config=config, entry_type=entry_type)


def filter_tree(
    entries: Sequence[TreeEntry | dict[str, Any]],
    config: TreeFilterConfig | None = None,
) -> list[TreeEntry]:
    """Filter tree entries using the default discovery filter."""
    return get_default_filter().filter_tree(entries, config=config)
