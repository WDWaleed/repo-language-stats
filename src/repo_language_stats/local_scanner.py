"""Local filesystem repository scanner.

Walks a directory on disk and produces the same AggregateStats that
scan_repositories() yields, but with zero HTTP requests and no token
requirement.  All existing filtering, classification, counting, and
notebook-parsing logic is reused unchanged.
"""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Sequence

from repo_language_stats.benchmark import BenchmarkCollector
from repo_language_stats.counting import (
    AggregateStats,
    StatsAccumulator,
    count_bytes,
    count_lines,
)
from repo_language_stats.discovery import (
    TreeEntry,
    TreeFilterConfig,
    filter_tree,
)
from repo_language_stats.language import classify, is_notebook
from repo_language_stats.notebook import parse_notebook

logger = logging.getLogger(__name__)


DEFAULT_LOCAL_EXCLUDED_DIRS: frozenset[str] = frozenset(
    {
        ".git",
        ".svn",
        ".hg",
        ".venv",
        "venv",
        ".env",
        ".pytest_cache",
        ".mypy_cache",
        ".ruff_cache",
        "__pycache__",
        ".tox",
        ".nox",
    }
)


def _walk_directory(root: Path) -> list[TreeEntry]:
    """Recursively walk *root* and return one TreeEntry per regular file.

    - Standard VCS metadata, virtual environments, and cache directories
      are pruned during traversal for performance and accurate counts.
    - Paths are stored relative to *root* using POSIX separators so they
      are identical in shape to what the GitHub Git Trees API returns.
    """
    entries: list[TreeEntry] = []
    root_resolved = root.resolve()
    for dirpath, dirnames, filenames in os.walk(root_resolved):
        dirnames[:] = [d for d in dirnames if d not in DEFAULT_LOCAL_EXCLUDED_DIRS]

        rel_dir = Path(dirpath).relative_to(root_resolved)
        for fname in filenames:
            rel_file = (rel_dir / fname).as_posix() if str(rel_dir) != "." else fname
            entries.append(TreeEntry(path=rel_file, type="blob"))

    return entries


def _process_file(
    abs_path: Path,
    rel_path: str,
    repo_name: str,
    ipynb_language: str | None,
    accumulator: StatsAccumulator,
    bm: BenchmarkCollector | None,
) -> None:
    """Read one file from disk and accumulate its statistics."""
    try:
        content: bytes = abs_path.read_bytes()
    except OSError as exc:
        logger.warning("Could not read %s: %s", abs_path, exc)
        return

    if is_notebook(rel_path):
        if bm:
            with bm.measure("parse_notebook"):
                nb_res = parse_notebook(
                    content=content,
                    fallback_language=ipynb_language,
                    file_path=f"{repo_name}/{rel_path}",
                )
        else:
            nb_res = parse_notebook(
                content=content,
                fallback_language=ipynb_language,
                file_path=f"{repo_name}/{rel_path}",
            )

        if nb_res:
            if nb_res.language in ("Python", "Jupyter (Python)"):
                lang_name = "Python"
            elif not nb_res.language.startswith("Jupyter") and nb_res.language != "Unknown (notebook)":
                lang_name = f"Jupyter ({nb_res.language})"
            else:
                lang_name = nb_res.language

            if bm:
                with bm.measure("aggregation"):
                    accumulator.add_stats(
                        language=lang_name,
                        bytes_count=nb_res.total_bytes,
                        lines_count=nb_res.total_lines,
                        files_count=1,
                        repo_name=repo_name,
                    )
                bm.record_source_bytes(nb_res.total_bytes)
                bm.record_file_processed(lines=nb_res.total_lines)
            else:
                accumulator.add_stats(
                    language=lang_name,
                    bytes_count=nb_res.total_bytes,
                    lines_count=nb_res.total_lines,
                    files_count=1,
                    repo_name=repo_name,
                )
    else:
        if bm:
            with bm.measure("classify"):
                lang = classify(rel_path)
        else:
            lang = classify(rel_path)

        if lang:
            if bm:
                with bm.measure("count_metrics"):
                    b_cnt = count_bytes(content)
                    l_cnt = count_lines(content)
                with bm.measure("aggregation"):
                    accumulator.add_stats(
                        language=lang,
                        bytes_count=b_cnt,
                        lines_count=l_cnt,
                        files_count=1,
                        repo_name=repo_name,
                    )
                bm.record_source_bytes(b_cnt)
                bm.record_file_processed(lines=l_cnt)
            else:
                b_cnt = count_bytes(content)
                l_cnt = count_lines(content)
                accumulator.add_stats(
                    language=lang,
                    bytes_count=b_cnt,
                    lines_count=l_cnt,
                    files_count=1,
                    repo_name=repo_name,
                )


def local_scan(
    path: Path | str,
    filter_config: TreeFilterConfig | None = None,
    ipynb_language: str | None = None,
    benchmark: BenchmarkCollector | None = None,
) -> AggregateStats:
    """Scan a local directory and return language statistics.

    Parameters
    ----------
    path:
        Root directory to scan.  Must exist and be a directory.
    filter_config:
        Filtering options (vendored, generated, docs, default-excluded,
        custom globs).  Defaults to :class:`TreeFilterConfig` defaults.
    ipynb_language:
        Override language for Jupyter notebooks whose kernel cannot be
        auto-detected.
    benchmark:
        Optional :class:`BenchmarkCollector` to record CPU-side timings.
        Network categories will remain at zero — a local scan produces a
        pure CPU profile.

    Returns
    -------
    AggregateStats
        Identical shape to what ``scan_repositories()`` returns, so all
        existing reporting / output flags work without modification.
    """
    root = Path(path).resolve()
    if not root.exists():
        raise FileNotFoundError(f"Local path does not exist: {root}")
    if not root.is_dir():
        raise NotADirectoryError(f"Local path is not a directory: {root}")

    repo_name = root.name
    cfg = filter_config or TreeFilterConfig()
    accumulator = StatsAccumulator(username=str(root))
    bm = benchmark

    logger.info("Local scan: walking %s", root)
    accumulator.start_repo(repo_name)

    if bm:
        bm.repos_benchmarked += 1

    # --- Walk directory tree ------------------------------------------------
    all_entries: list[TreeEntry] = _walk_directory(root)
    logger.debug("Found %d total filesystem entries under %s", len(all_entries), root)

    # --- Apply the same filter_tree logic used for GitHub trees -------------
    if bm:
        with bm.measure("filter_tree"):
            eligible: list[TreeEntry] = filter_tree(all_entries, config=cfg)
    else:
        eligible = filter_tree(all_entries, config=cfg)

    logger.debug(
        "Local scan: %d eligible files out of %d total entries in %s",
        len(eligible),
        len(all_entries),
        repo_name,
    )

    # --- Process each eligible file ----------------------------------------
    for entry in eligible:
        abs_path = root / entry.path
        _process_file(
            abs_path=abs_path,
            rel_path=entry.path,
            repo_name=repo_name,
            ipynb_language=ipynb_language,
            accumulator=accumulator,
            bm=bm,
        )

    accumulator.finish_repo(skipped=False)
    result = accumulator.finalize()

    logger.info(
        "Local scan complete: %d files processed across %d language(s)",
        sum(ls.file_count for ls in result.aggregate.values()),
        len(result.aggregate),
    )
    return result
