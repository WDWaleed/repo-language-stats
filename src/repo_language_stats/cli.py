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
from repo_language_stats.reporting import display_report, render_report

logger = logging.getLogger("repo_language_stats")


def build_parser() -> argparse.ArgumentParser:
    """Build the argument parser for repo-language-stats."""
    parser = argparse.ArgumentParser(
        prog="repo-language-stats",
        description="Compute aggregate programming-language statistics across a GitHub user's repositories or for a single repository.",
    )

    parser.add_argument(
        "target",
        metavar="TARGET",
        help="GitHub username or single repository in 'owner/repo' format to scan.",
    )
    parser.add_argument(
        "--repo",
        default=None,
        help="Specific repository name to scan (when TARGET is an owner/username).",
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
        "--include-private",
        action="store_true",
        default=False,
        help="Include private repositories (requires a token with 'repo' scope; "
             "only works when scanning your own account).",
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
        "--all",
        action="store_true",
        dest="include_all",
        default=False,
        help="Include data and configuration files excluded by default (CSV, YAML, TOML, SVG, Dotenv, JSON, and JSON with Comments).",
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


def scan_repositories(
    target_name: str,
    repos: Sequence[RepoInfo],
    client: GitHubAPIClient,
    filter_config: TreeFilterConfig | None = None,
    ipynb_language: str | None = None,
    progress: Progress | None = None,
) -> AggregateStats:
    """Scan a sequence of repositories and compute aggregated language statistics."""
    cfg = filter_config or TreeFilterConfig()
    accumulator = StatsAccumulator(username=target_name)

    if not repos:
        logger.warning("No repositories found to scan for %s.", target_name)
        return accumulator.finalize()

    task_id = None
    if progress:
        task_id = progress.add_task(f"[cyan]Scanning {target_name}...", total=len(repos))

    for repo in repos:
        logger.info(
            "Scanning %s repository %s/%s (branch: %s)...",
            "private" if repo.is_private else "public",
            repo.owner,
            repo.name,
            repo.default_branch,
        )
        accumulator.start_repo(repo.name)

        try:
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
                        if nb_res.language in ("Python", "Jupyter (Python)"):
                            lang_name = "Python"
                        elif not nb_res.language.startswith("Jupyter") and nb_res.language != "Unknown (notebook)":
                            lang_name = f"Jupyter ({nb_res.language})"
                        else:
                            lang_name = nb_res.language
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
        except Exception as exc:
            logger.warning("Error scanning repository %s/%s: %s. Skipping.", repo.owner, repo.name, exc)
            accumulator.finish_repo(skipped=True)
        finally:
            if progress and task_id is not None:
                progress.advance(task_id)

    return accumulator.finalize()


def scan_user(
    username: str,
    client: GitHubAPIClient,
    filter_config: TreeFilterConfig | None = None,
    include_forks: bool = False,
    include_private: bool = False,
    ipynb_language: str | None = None,
    progress: Progress | None = None,
) -> AggregateStats:
    """Scan all repositories for a GitHub user and compute language statistics."""
    logger.info("Listing repositories for user %s...", username)
    repos = client.list_repos(
        username=username,
        include_forks=include_forks,
        include_private=include_private,
    )
    if include_private and repos:
        private_count = sum(1 for r in repos if r.is_private)
        if private_count == 0:
            logger.warning(
                "No private repositories found for %s. "
                "Ensure your token has the 'repo' scope (classic PAT) "
                "or Contents: Read permission (fine-grained PAT).",
                username,
            )
    return scan_repositories(
        target_name=username,
        repos=repos,
        client=client,
        filter_config=filter_config,
        ipynb_language=ipynb_language,
        progress=progress,
    )


def scan_single_repo(
    owner: str,
    repo_name: str,
    client: GitHubAPIClient,
    filter_config: TreeFilterConfig | None = None,
    ipynb_language: str | None = None,
    progress: Progress | None = None,
) -> AggregateStats:
    """Scan a single repository and compute language statistics."""
    full_name = f"{owner}/{repo_name}"
    logger.info("Fetching repository metadata for %s...", full_name)
    repo = client.get_repo(owner=owner, repo=repo_name)
    if not repo:
        logger.warning("Repository %s not found or inaccessible.", full_name)
        return AggregateStats(username=full_name)

    return scan_repositories(
        target_name=full_name,
        repos=[repo],
        client=client,
        filter_config=filter_config,
        ipynb_language=ipynb_language,
        progress=progress,
    )


def main(argv: Sequence[str] | None = None) -> int:
    """Main CLI entry point."""
    parser = build_parser()
    args = parser.parse_args(argv)

    configure_logging(args.verbose)

    # Determine whether target is a single repo (owner/repo or --repo flag) or a user
    target_str = args.target.strip()
    if "/" in target_str:
        parts = target_str.split("/", 1)
        owner = parts[0].strip()
        repo_name = parts[1].strip()
        is_single_repo = True
    elif args.repo:
        owner = target_str
        repo_name = args.repo.strip()
        is_single_repo = True
    else:
        owner = target_str
        repo_name = None
        is_single_repo = False

    filter_cfg = TreeFilterConfig(
        include_generated=args.include_generated,
        include_vendored=args.include_vendored,
        include_docs=args.include_docs,
        include_all=args.include_all,
        exclude_patterns=args.exclude_patterns or [],
    )

    console = Console(stderr=True)
    show_progress = args.format == "table" and args.output is None

    try:
        if args.include_private and not args.token:
            sys.stderr.write(
                "Error: --include-private requires a GitHub token. "
                "Set GITHUB_TOKEN or pass --token.\n"
            )
            return 1

        with GitHubAPIClient(token=args.token) as client:
            if args.include_private:
                if is_single_repo:
                    logger.warning(
                        "--include-private is not needed for single-repo mode; "
                        "private repositories are already accessible if your token has access."
                    )
                else:
                    authenticated_user = client.get_authenticated_user()
                    if authenticated_user is None:
                        sys.stderr.write(
                            "Error: Could not verify token. "
                            "Ensure your GITHUB_TOKEN is valid.\n"
                        )
                        return 1

                    if authenticated_user.lower() != owner.lower():
                        sys.stderr.write(
                            f"Error: --include-private can only scan your own account. "
                            f"Token belongs to '{authenticated_user}' but target is '{owner}'.\n"
                        )
                        return 1

            if is_single_repo and repo_name:
                scan_action = lambda prog: scan_single_repo(
                    owner=owner,
                    repo_name=repo_name,
                    client=client,
                    filter_config=filter_cfg,
                    ipynb_language=args.ipynb_language,
                    progress=prog,
                )
            else:
                scan_action = lambda prog: scan_user(
                    username=owner,
                    client=client,
                    filter_config=filter_cfg,
                    include_forks=args.include_forks,
                    include_private=args.include_private,
                    ipynb_language=args.ipynb_language,
                    progress=prog,
                )

            if show_progress:
                with Progress(
                    SpinnerColumn(),
                    TextColumn("[progress.description]{task.description}"),
                    BarColumn(),
                    MofNCompleteColumn(),
                    TimeElapsedColumn(),
                    console=console,
                ) as progress:
                    stats = scan_action(progress)
            else:
                stats = scan_action(None)

        if args.output:
            output_str = render_report(
                stats=stats,
                fmt=args.format,
                per_repo=args.per_repo,
                show_files=args.show_files,
            )
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(output_str, encoding="utf-8")
        else:
            display_report(
                stats=stats,
                fmt=args.format,
                per_repo=args.per_repo,
                show_files=args.show_files,
            )

        return 0

    except KeyboardInterrupt:
        sys.stderr.write("\nScan aborted by user.\n")
        return 130
    except Exception as exc:
        logger.exception("An error occurred during scanning: %s", exc)
        sys.stderr.write(f"Error: {exc}\n")
        return 1

