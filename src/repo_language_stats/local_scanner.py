"""Local filesystem repository scanner.

Walks a directory on disk and produces the same AggregateStats that
scan_repositories() yields, but with zero HTTP requests and no token
requirement.  All existing filtering, classification, counting, and
notebook-parsing logic is reused unchanged.
"""

from __future__ import annotations

from fnmatch import fnmatch
import logging
import os
from pathlib import Path
import subprocess
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


def _get_git_working_tree_files(root: Path) -> list[str] | None:
    """Query git for tracked and non-ignored working tree files.

    Runs ``git ls-files -z --cached --others --exclude-standard`` in *root*.
    Returns a list of relative POSIX path strings if inside a git repository
    and git is installed; returns None otherwise.
    """
    try:
        proc = subprocess.run(
            ["git", "ls-files", "-z", "--cached", "--others", "--exclude-standard"],
            cwd=str(root),
            capture_output=True,
            check=False,
        )
        if proc.returncode != 0:
            return None
        raw = proc.stdout
        if not raw:
            return []
        items = raw.split(b"\0")
        files: list[str] = []
        for item in items:
            if not item:
                continue
            path_str = item.decode("utf-8", errors="replace").replace("\\", "/")
            files.append(path_str)
        return files
    except (FileNotFoundError, OSError):
        return None


def _parse_gitignore(gitignore_path: Path) -> list[tuple[bool, str]]:
    """Parse a .gitignore file into a list of (is_negation, pattern) pairs."""
    rules: list[tuple[bool, str]] = []
    if not gitignore_path.is_file():
        return rules
    try:
        content = gitignore_path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return rules

    for line in content.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        is_neg = False
        if line.startswith("!"):
            is_neg = True
            line = line[1:].strip()
        rules.append((is_neg, line))
    return rules


def _matches_gitignore_rules(
    rel_path: str,
    is_dir: bool,
    rules: list[tuple[bool, str]],
) -> bool:
    """Check if a relative path matches parsed gitignore rules."""
    norm_path = rel_path.replace("\\", "/").strip("/")
    parts = norm_path.split("/")
    ignored = False

    for is_neg, pat in rules:
        pat = pat.replace("\\", "/")
        dir_only = pat.endswith("/")
        pat_clean = pat.rstrip("/")

        if dir_only and not is_dir:
            # Check if any parent directory component matches
            matched = False
            for i in range(len(parts) - 1):
                sub_dir = "/".join(parts[: i + 1])
                sub_name = parts[i]
                if "/" in pat_clean:
                    if fnmatch(sub_dir, pat_clean.lstrip("/")):
                        matched = True
                        break
                else:
                    if fnmatch(sub_name, pat_clean):
                        matched = True
                        break
            if matched:
                ignored = not is_neg
            continue

        if "/" in pat_clean:
            rule_pat = pat_clean.lstrip("/")
            if fnmatch(norm_path, rule_pat) or fnmatch(norm_path, f"{rule_pat}/*"):
                ignored = not is_neg
        else:
            if fnmatch(parts[-1], pat_clean) or any(fnmatch(p, pat_clean) for p in parts):
                ignored = not is_neg

    return ignored


def _walk_directory(root: Path, respect_gitignore: bool = True) -> list[TreeEntry]:
    """Recursively walk *root* and return one TreeEntry per eligible regular file.

    - If *respect_gitignore* is True, git-native discovery is attempted first.
      If git is unavailable or the directory is not a Git repo, falls back to
      pure-Python .gitignore pattern matching.
    - Standard VCS metadata, virtual environments, and cache directories
      are always pruned during directory walking.
    - Paths are stored relative to *root* using POSIX separators.
    """
    root_resolved = root.resolve()

    if respect_gitignore:
        git_files = _get_git_working_tree_files(root_resolved)
        if git_files is not None:
            entries: list[TreeEntry] = []
            for rel in git_files:
                abs_f = root_resolved / rel
                if abs_f.is_file():
                    entries.append(TreeEntry(path=rel, type="blob"))
            return entries

    # Fallback or respect_gitignore=False: standard filesystem walk
    rules: list[tuple[bool, str]] = []
    if respect_gitignore:
        rules = _parse_gitignore(root_resolved / ".gitignore")

    entries = []
    for dirpath, dirnames, filenames in os.walk(root_resolved):
        dirnames[:] = [d for d in dirnames if d not in DEFAULT_LOCAL_EXCLUDED_DIRS]

        rel_dir = Path(dirpath).relative_to(root_resolved)

        if respect_gitignore and rules:
            pruned_dirs = []
            for d in dirnames:
                dir_rel = (rel_dir / d).as_posix() if str(rel_dir) != "." else d
                if not _matches_gitignore_rules(dir_rel, is_dir=True, rules=rules):
                    pruned_dirs.append(d)
            dirnames[:] = pruned_dirs

        for fname in filenames:
            rel_file = (rel_dir / fname).as_posix() if str(rel_dir) != "." else fname
            if respect_gitignore and rules and _matches_gitignore_rules(rel_file, is_dir=False, rules=rules):
                continue
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
    respect_gitignore: bool = True,
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
    respect_gitignore:
        Whether to exclude files matched by .gitignore.  Defaults to True.

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

    logger.info("Local scan: walking %s (respect_gitignore=%s)", root, respect_gitignore)
    accumulator.start_repo(repo_name)

    if bm:
        bm.repos_benchmarked += 1

    # --- Walk directory tree ------------------------------------------------
    all_entries: list[TreeEntry] = _walk_directory(root, respect_gitignore=respect_gitignore)
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
