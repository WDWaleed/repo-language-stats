"""CLI argument parsing and main execution orchestration."""

from __future__ import annotations

import argparse
import logging
import os
from pathlib import Path
import sys
from typing import Sequence

from rich.console import Console
from rich.progress import (
    BarColumn,
    MofNCompleteColumn,
    Progress,
    SpinnerColumn,
    TextColumn,
    TimeElapsedColumn,
)

from repo_language_stats.counting import (
    AggregateStats,
    StatsAccumulator,
)
from repo_language_stats.discovery import (
    TreeFilterConfig,
    filter_tree,
)
from repo_language_stats.github_api import GitHubAPIClient
from repo_language_stats.language import classify, is_notebook
from repo_language_stats.notebook import parse_notebook
from repo_language_stats.reporting import render_report

logger = logging.getLogger("repo_language_stats")


def build_parser() -> argparse.ArgumentParser:
    """Build the argument parser for repo-language-stats."""
    parser = argparse.ArgumentParser(
        prog="repo-language-stats",
        description="Compute aggregate programming-language statistics across a GitHub user's repositories.",
    )

    parser.add_argument(
        "username",
        help="GitHub username whose repositories will be scanned.",
    )
    parser.add_argument(
        "--token",
        default=os.getenv("GITHUB_TOKEN"),
        help="GitHub personal access token (defaults to GITHUB_TOKEN environment variable).",
    )
    parser.add_argument(
        "--include-forks",
        action="store_true",
        default=False,
        help="Include forked repositories in the statistics (excluded by default).",
    )
    parser.add_argument(
        "--include-generated",
        action="store_true",
        default=False,
        help="Include generated and minified files in the statistics.",
    )
    parser.add_argument(
        "--include-vendored",
        action="store_true",
        default=False,
        help="Include vendored dependencies in the statistics.",
    )
    parser.add_argument(
        "--include-docs",
        action="store_true",
        default=False,
        help="Include documentation and prose files (e.g. .md, .rst, .txt).",
    )
    parser.add_argument(
        "--exclude-pattern",
        action="append",
        dest="exclude_patterns",
        default=[],
        help="Glob pattern for paths or filenames to exclude (can be specified multiple times).",
    )
    parser.add_argument(
        "--per-repo",
        action="store_true",
        default=False,
        help="Display per-repository breakdown in addition to aggregate summary.",
    )
    parser.add_argument(
        "--show-files",
        action="store_true",
        default=False,
        help="Include file count column in output.",
    )
    parser.add_argument(
        "--format",
        choices=["table", "json", "csv"],
        default="table",
        help="Output format: table (default), json, or csv.",
    )
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        default=None,
        help="Write output to specified file instead of stdout.",
    )
    parser.add_argument(
        "--ipynb-language",
        default=None,
        help="Override language for Jupyter notebooks whose kernel cannot be auto-detected.",
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="count",
        default=0,
        help="Increase logging verbosity (-v for INFO, -vv for DEBUG).",
    )

    return parser


def configure_logging(verbosity: int) -> None:
    """Configure standard logging level based on verbosity count."""
    if verbosity >= 2:
        level = logging.DEBUG
    elif verbosity == 1:
        level = logging.INFO
    else:
        level = logging.WARNING

    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )


def scan_user(
    username: str,
    client: GitHubAPIClient,
    filter_config: TreeFilterConfig | None = None,
    include_forks: bool = False,
    ipynb_language: str | None = None,
    progress: Progress | None = None,
) -> AggregateStats:
    """Scan repositories for a GitHub user and compute language statistics."""
    cfg = filter_config or TreeFilterConfig()
    accumulator = StatsAccumulator(username=username)

    logger.info("Listing repositories for user %s...", username)
    repos = client.list_repos(username=username, include_forks=include_forks)

    if not repos:
        logger.warning("No repositories found for user %s.", username)
        return accumulator.finalize()

    task_id = None
    if progress:
        task_id = progress.add_task(f"[cyan]Scanning {username}'s repositories...", total=len(repos))

    for repo in repos:
        logger.info("Scanning repository %s/%s (branch: %s)...", repo.owner, repo.name, repo.default_branch)
        accumulator.start_repo(repo.name)

        tree_entries, is_truncated = client.get_tree(
            owner=repo.owner,
            repo=repo.name,
            sha=repo.default_branch,
        )

        if not tree_entries:
            logger.info("Repository %s/%s has no accessible tree entries. Skipping.", repo.owner, repo.name)
            accumulator.finish_repo(skipped=True)
            if progress and task_id is not None:
                progress.advance(task_id)
            continue

        eligible = filter_tree(tree_entries, config=cfg)
        logger.debug("Found %d eligible files out of %d tree entries in %s", len(eligible), len(tree_entries), repo.name)

        for entry in eligible:
            blob_content = client.get_blob(owner=repo.owner, repo=repo.name, sha=entry.sha)
            if blob_content is None:
                continue

            if is_notebook(entry.path):
                nb_res = parse_notebook(
                    content=blob_content,
                    fallback_language=ipynb_language,
                    file_path=f"{repo.name}/{entry.path}",
                )
                if nb_res:
                    lang_name = f"Jupyter ({nb_res.language})" if not nb_res.language.startswith("Jupyter") else nb_res.language
                    accumulator.add_stats(
                        language=lang_name,
                        bytes_count=nb_res.total_bytes,
                        lines_count=nb_res.total_lines,
                        files_count=1,
                        repo_name=repo.name,
                    )
            else:
                lang = classify(entry.path)
                if lang:
                    accumulator.add_file(
                        language=lang,
                        content=blob_content,
                        repo_name=repo.name,
                    )

        accumulator.finish_repo(skipped=False)
        if progress and task_id is not None:
            progress.advance(task_id)

    return accumulator.finalize()


def main(argv: Sequence[str] | None = None) -> int:
    """Main CLI entry point."""
    parser = build_parser()
    args = parser.parse_args(argv)

    configure_logging(args.verbose)

    filter_cfg = TreeFilterConfig(
        include_generated=args.include_generated,
        include_vendored=args.include_vendored,
        include_docs=args.include_docs,
        exclude_patterns=args.exclude_patterns or [],
    )

    console = Console(stderr=True)
    show_progress = args.format == "table" and args.output is None

    try:
        with GitHubAPIClient(token=args.token) as client:
            if show_progress:
                with Progress(
                    SpinnerColumn(),
                    TextColumn("[progress.description]{task.description}"),
                    BarColumn(),
                    MofNCompleteColumn(),
                    TimeElapsedColumn(),
                    console=console,
                ) as progress:
                    stats = scan_user(
                        username=args.username,
                        client=client,
                        filter_config=filter_cfg,
                        include_forks=args.include_forks,
                        ipynb_language=args.ipynb_language,
                        progress=progress,
                    )
            else:
                stats = scan_user(
                    username=args.username,
                    client=client,
                    filter_config=filter_cfg,
                    include_forks=args.include_forks,
                    ipynb_language=args.ipynb_language,
                    progress=None,
                )

        output_str = render_report(
            stats=stats,
            fmt=args.format,
            per_repo=args.per_repo,
            show_files=args.show_files,
        )

        if args.output:
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(output_str, encoding="utf-8")
        else:
            sys.stdout.write(output_str)
            sys.stdout.flush()

        return 0

    except KeyboardInterrupt:
        sys.stderr.write("\nScan aborted by user.\n")
        return 130
    except Exception as exc:
        logger.exception("An error occurred during scanning: %s", exc)
        sys.stderr.write(f"Error: {exc}\n")
        return 1
