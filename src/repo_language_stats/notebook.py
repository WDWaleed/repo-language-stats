"""Jupyter notebook (.ipynb) parser and code cell extractor."""

from __future__ import annotations

from dataclasses import dataclass
from fnmatch import fnmatch
import json
import logging
from pathlib import Path
from typing import Any

import nbformat

from repo_language_stats.counting import count_bytes, count_lines

logger = logging.getLogger(__name__)

# Patterns for matching kernelspec.name
KERNEL_NAME_PATTERNS: list[tuple[str, str]] = [
    ("python*", "Python"),
    ("ir", "R"),
    ("r", "R"),
    ("julia*", "Julia"),
    ("xeus-cling*", "C++"),
    ("cling*", "C++"),
    ("rust", "Rust"),
    ("bash", "Shell"),
    ("calysto_bash", "Shell"),
    ("sh", "Shell"),
    ("javascript*", "JavaScript"),
    ("tslab", "TypeScript"),
    ("typescript*", "TypeScript"),
    ("kotlin*", "Kotlin"),
    ("scala*", "Scala"),
]

# Canonical normalization for language strings
CANONICAL_LANGUAGE_NAMES: dict[str, str] = {
    "python": "Python",
    "r": "R",
    "julia": "Julia",
    "c++": "C++",
    "cpp": "C++",
    "c": "C",
    "rust": "Rust",
    "javascript": "JavaScript",
    "js": "JavaScript",
    "typescript": "TypeScript",
    "ts": "TypeScript",
    "bash": "Shell",
    "sh": "Shell",
    "shell": "Shell",
    "scala": "Scala",
    "kotlin": "Kotlin",
    "go": "Go",
    "ruby": "Ruby",
    "sql": "SQL",
}


@dataclass
class NotebookParseResult:
    """Result of parsing a Jupyter notebook file."""

    language: str
    code_text: str
    total_bytes: int
    total_lines: int


def normalize_language_name(lang: str) -> str:
    """Normalize raw language identifier to standard display name."""
    cleaned = lang.strip().lower()
    if cleaned in CANONICAL_LANGUAGE_NAMES:
        return CANONICAL_LANGUAGE_NAMES[cleaned]
    return lang.strip().capitalize()


def determine_notebook_language(
    metadata: dict[str, Any],
    fallback_language: str | None = None,
    file_path: str = "",
) -> str:
    """Determine the programming language of a notebook from its metadata.

    Resolution order:
    1. Primary: metadata.kernelspec.language
    2. Fallback 1: metadata.kernelspec.name matched against known patterns
    3. Fallback 2: metadata.language_info.name
    4. Override / Unknown: user-provided fallback_language or 'Unknown (notebook)'
    """
    kernelspec = metadata.get("kernelspec", {})
    if isinstance(kernelspec, dict):
        # 1. Primary: kernelspec.language
        lang = kernelspec.get("language")
        if lang and isinstance(lang, str) and lang.strip():
            return normalize_language_name(lang)

        # 2. Fallback 1: kernelspec.name
        name = kernelspec.get("name")
        if name and isinstance(name, str):
            name_clean = name.strip().lower()
            for pattern, target_lang in KERNEL_NAME_PATTERNS:
                if fnmatch(name_clean, pattern):
                    return target_lang

    # 3. Fallback 2: language_info.name
    lang_info = metadata.get("language_info", {})
    if isinstance(lang_info, dict):
        name = lang_info.get("name")
        if name and isinstance(name, str) and name.strip():
            return normalize_language_name(name)

    # 4. Fallback / Override or Unknown
    if fallback_language:
        return fallback_language

    logger.warning("Could not determine language for notebook %s; recording as 'Unknown (notebook)'", file_path)
    return "Unknown (notebook)"


def parse_notebook(
    content: str | bytes | Path,
    fallback_language: str | None = None,
    file_path: str = "",
) -> NotebookParseResult | None:
    """Parse a Jupyter notebook, extracting code cells and determining its language.

    Returns None if the notebook is malformed or invalid JSON.
    Never raises on malformed files.
    """
    path_display = file_path or (str(content) if isinstance(content, Path) else "notebook")

    try:
        if isinstance(content, Path):
            content_str = content.read_text(encoding="utf-8", errors="replace")
        elif isinstance(content, bytes):
            content_str = content.decode("utf-8", errors="replace")
        else:
            content_str = content

        nb = nbformat.reads(content_str, as_version=4)
    except (
        nbformat.reader.NotJSONError,
        nbformat.ValidationError,
        json.JSONDecodeError,
        KeyError,
        Exception,
    ) as exc:
        logger.warning("Failed to parse notebook %s: %s", path_display, exc)
        return None

    # Determine notebook language
    metadata = getattr(nb, "metadata", {}) or {}
    language = determine_notebook_language(
        metadata=dict(metadata),
        fallback_language=fallback_language,
        file_path=path_display,
    )

    # Extract code cells
    cells = getattr(nb, "cells", []) or []
    code_cell_texts: list[str] = []

    for cell in cells:
        cell_type = getattr(cell, "cell_type", None) or cell.get("cell_type")
        if cell_type != "code":
            continue

        raw_source = getattr(cell, "source", "") or cell.get("source", "")
        cell_text = str(raw_source)

        code_cell_texts.append(cell_text)

    # Join selected code cells separated by a single newline
    joined_text = "\n".join(code_cell_texts) if code_cell_texts else ""

    tot_bytes = count_bytes(joined_text)
    tot_lines = count_lines(joined_text)

    return NotebookParseResult(
        language=language,
        code_text=joined_text,
        total_bytes=tot_bytes,
        total_lines=tot_lines,
    )
