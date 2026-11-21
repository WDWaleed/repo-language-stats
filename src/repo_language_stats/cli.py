"""CLI argument parsing and main execution orchestration."""

from __future__ import annotations

import argparse
import logging
import os
from pathlib import Path
import sys
from typing import Sequence
from urllib.parse import urlparse

from rich.console import Console
from rich.progress import (
    BarColumn,
    MofNCompleteColumn,
    Progress,
    SpinnerColumn,
    TextColumn,
    TimeElapsedColumn,
)

from repo_language_stats.benchmark import BenchmarkCollector
from repo_language_stats.counting import (
    AggregateStats,
    StatsAccumulator,
    count_bytes,
    count_lines,
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

_USE_ENV_TOKEN = "__USE_ENV_TOKEN__"

OPTS_WITH_ARG = {
    "--repo",
    "-b",
    "--branch",
    "--exclude-pattern",
    "--format",
    "-o",
    "--output",
    "--ipynb-language",
}


def get_env_github_token(env_path: Path | str | None = None) -> str | None:
    """Read GITHUB_TOKEN from .env file if available, falling back to os.environ."""
    if env_path is not None:
        p = Path(env_path)
        candidates = [p] if p.is_file() else [p / ".env"]
    else:
        cur = Path.cwd().resolve()
        candidates = [cur / ".env"] + [parent / ".env" for parent in cur.parents]

    for env_file in candidates:
        if env_file.is_file():
            try:
                for line in env_file.read_text(encoding="utf-8", errors="replace").splitlines():
                    line = line.strip()
                    if not line or line.startswith("#"):
                        continue
                    if line.startswith("export "):
                        line = line[len("export "):].strip()
                    if "=" not in line:
                        continue
                    key, val = line.split("=", 1)
                    key = key.strip()
                    val = val.strip()
                    if (val.startswith('"') and val.endswith('"')) or (val.startswith("'") and val.endswith("'")):
                        val = val[1:-1]
                    else:
                        if " #" in val:
                            val = val.split(" #", 1)[0].strip()
                    if key == "GITHUB_TOKEN" and val:
                        return val
            except OSError:
                pass
            if env_path is None:
                break
    return os.getenv("GITHUB_TOKEN")


class TokenAction(argparse.Action):
    """Custom action for --token to load from .env when passed without a value."""

    def __call__(
        self,
        parser: argparse.ArgumentParser,
        namespace: argparse.Namespace,
        values: str | None,
        option_string: str | None = None,
    ) -> None:
        if values == _USE_ENV_TOKEN or values is None:
            token = get_env_github_token()
            setattr(namespace, self.dest, token)
        else:
            setattr(namespace, self.dest, values)


def preprocess_token_args(argv: Sequence[str]) -> list[str]:
    """Preprocess arguments so '--token <target>' correctly attributes <target> as positional TARGET."""
    new_argv = list(argv)
    i = 0
    while i < len(new_argv):
        if new_argv[i] == "--token":
            t_idx = i
            # Check if followed by an argument that does not start with '-'
            if t_idx + 1 < len(new_argv) and not new_argv[t_idx + 1].startswith("-"):
                # Count non-flag arguments outside options with args
                idx = 0
                free_args: list[tuple[int, str]] = []
                while idx < len(new_argv):
                    item = new_argv[idx]
                    if any(item == opt or item.startswith(opt + "=") for opt in OPTS_WITH_ARG):
                        if "=" in item:
                            idx += 1
                        else:
                            idx += 2
                        continue
                    elif item == "--token":
                        idx += 1
                        continue
                    elif not item.startswith("-"):
                        free_args.append((idx, item))
                    idx += 1
                # If only 1 free arg total, it must be the required target positional!
                if len(free_args) == 1 and free_args[0][0] == t_idx + 1:
                    new_argv.insert(t_idx + 1, _USE_ENV_TOKEN)
                    i += 1
        i += 1
    return new_argv


class RepoStatsArgumentParser(argparse.ArgumentParser):
    """ArgumentParser that preprocesses token arguments before parsing."""

    def parse_known_args(
        self,
        args: Sequence[str] | None = None,
        namespace: argparse.Namespace | None = None,
    ) -> tuple[argparse.Namespace, list[str]]:
        if args is None:
            args = sys.argv[1:]
        args = preprocess_token_args(args)
        return super().parse_known_args(args, namespace=namespace)


def build_parser() -> argparse.ArgumentParser:
    """Build the argument parser for repo-language-stats."""
    parser = RepoStatsArgumentParser(
        prog="repo-language-stats",
        description="Compute aggregate programming-language statistics across a GitHub user's repositories or for a single repository.",
    )

    parser.add_argument(
        "target",
        metavar="TARGET",
        help="GitHub username, repository in 'owner/repo' format, or GitHub URL to scan.",
    )
    parser.add_argument(
        "--repo",
        default=None,
        help="Specific repository name to scan (when TARGET is an owner/username).",
    )
    parser.add_argument(
        "-b",
        "--branch",
        default=None,
        metavar="BRANCH",
        help="Specific branch or Git ref to scan (single repository mode only; defaults to repository's default branch).",
    )
    parser.add_argument(
        "--token",
        nargs="?",
        const=_USE_ENV_TOKEN,
        default=os.getenv("GITHUB_TOKEN"),
        action=TokenAction,
        metavar="TOKEN",
        help="GitHub personal access token (if passed without a value, automatically uses GITHUB_TOKEN from .env; defaults to GITHUB_TOKEN environment variable).",
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
    benchmark: BenchmarkCollector | None = None,
) -> AggregateStats:
    """Scan a sequence of repositories and compute aggregated language statistics."""
    cfg = filter_config or TreeFilterConfig()
    accumulator = StatsAccumulator(username=target_name)
    bm = benchmark or client.benchmark

    if not repos:
        logger.warning("No repositories found to scan for %s.", target_name)
        if bm:
            with bm.measure("aggregation"):
                return accumulator.finalize()
        return accumulator.finalize()

    task_id = None
    if progress:
        task_id = progress.add_task(f"[cyan]Scanning {target_name}...", total=len(repos))

    for repo in repos:
        if bm:
            bm.repos_benchmarked += 1

        active_branch = repo.branch or repo.default_branch
        target_sha = repo.tree_sha or repo.default_branch
        logger.info(
            "Scanning %s repository %s/%s (branch: %s)...",
            "private" if repo.is_private else "public",
            repo.owner,
            repo.name,
            active_branch,
        )
        accumulator.start_repo(repo.name)

        try:
            tree_entries, is_truncated = client.get_tree(
                owner=repo.owner,
                repo=repo.name,
                sha=target_sha,
            )

            if not tree_entries:
                logger.info("Repository %s/%s has no accessible tree entries. Skipping.", repo.owner, repo.name)
                accumulator.finish_repo(skipped=True)
                if progress and task_id is not None:
                    progress.advance(task_id)
                continue

            if bm:
                with bm.measure("filter_tree"):
                    eligible = filter_tree(tree_entries, config=cfg)
            else:
                eligible = filter_tree(tree_entries, config=cfg)
            logger.debug("Found %d eligible files out of %d tree entries in %s", len(eligible), len(tree_entries), repo.name)

            for entry in eligible:
                blob_content = client.get_blob(owner=repo.owner, repo=repo.name, sha=entry.sha)
                if blob_content is None:
                    continue

                if is_notebook(entry.path):
                    if bm:
                        with bm.measure("parse_notebook"):
                            nb_res = parse_notebook(
                                content=blob_content,
                                fallback_language=ipynb_language,
                                file_path=f"{repo.name}/{entry.path}",
                            )
                    else:
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

                        if bm:
                            with bm.measure("aggregation"):
                                accumulator.add_stats(
                                    language=lang_name,
                                    bytes_count=nb_res.total_bytes,
                                    lines_count=nb_res.total_lines,
                                    files_count=1,
                                    repo_name=repo.name,
                                )
                            bm.record_source_bytes(nb_res.total_bytes)
                            bm.record_file_processed(lines=nb_res.total_lines)
                        else:
                            accumulator.add_stats(
                                language=lang_name,
                                bytes_count=nb_res.total_bytes,
                                lines_count=nb_res.total_lines,
                                files_count=1,
                                repo_name=repo.name,
                            )
                else:
                    if bm:
                        with bm.measure("classify"):
                            lang = classify(entry.path)
                    else:
                        lang = classify(entry.path)

                    if lang:
                        if bm:
                            with bm.measure("count_metrics"):
                                b_cnt = count_bytes(blob_content)
                                l_cnt = count_lines(blob_content)
                            with bm.measure("aggregation"):
                                accumulator.add_stats(
                                    language=lang,
                                    bytes_count=b_cnt,
                                    lines_count=l_cnt,
                                    files_count=1,
                                    repo_name=repo.name,
                                )
                            bm.record_source_bytes(b_cnt)
                            bm.record_file_processed(lines=l_cnt)
                        else:
                            accumulator.add_file(
                                language=lang,
                                content=blob_content,
                                repo_name=repo.name,
                            )

            if bm:
                with bm.measure("aggregation"):
                    accumulator.finish_repo(skipped=False)
            else:
                accumulator.finish_repo(skipped=False)
        except Exception as exc:
            logger.warning("Error scanning repository %s/%s: %s. Skipping.", repo.owner, repo.name, exc)
            accumulator.finish_repo(skipped=True)
        finally:
            if progress and task_id is not None:
                progress.advance(task_id)

    if bm:
        with bm.measure("aggregation"):
            return accumulator.finalize()
    return accumulator.finalize()


def scan_user(
    username: str,
    client: GitHubAPIClient,
    filter_config: TreeFilterConfig | None = None,
    include_forks: bool = False,
    include_private: bool = False,
    ipynb_language: str | None = None,
    progress: Progress | None = None,
    benchmark: BenchmarkCollector | None = None,
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
        benchmark=benchmark,
    )


def scan_single_repo(
    owner: str,
    repo_name: str,
    client: GitHubAPIClient,
    branch: str | None = None,
    filter_config: TreeFilterConfig | None = None,
    ipynb_language: str | None = None,
    progress: Progress | None = None,
    benchmark: BenchmarkCollector | None = None,
) -> AggregateStats | None:
    """Scan a single repository and compute language statistics."""
    full_name = f"{owner}/{repo_name}"
    logger.info("Fetching repository metadata for %s...", full_name)
    repo = client.get_repo(owner=owner, repo=repo_name)
    if not repo:
        logger.warning("Repository %s not found or inaccessible.", full_name)
        return AggregateStats(username=full_name)

    if branch:
        logger.info("Resolving branch/ref '%s' for %s...", branch, full_name)
        tree_sha = client.get_ref_tree_sha(owner=owner, repo=repo_name, ref=branch)
        if not tree_sha:
            sys.stderr.write(f"Error: Branch '{branch}' was not found in repository '{full_name}'.\n")
            return None
        repo.branch = branch
        repo.tree_sha = tree_sha

    stats = scan_repositories(
        target_name=full_name,
        repos=[repo],
        client=client,
        filter_config=filter_config,
        ipynb_language=ipynb_language,
        progress=progress,
        benchmark=benchmark,
    )
    if branch:
        stats.branch = branch
    return stats
    if branch:
        stats.branch = branch
    return stats


def parse_target_ref(target: str) -> tuple[str, str | None]:
    """Extract normalized target and optional branch ref from a target string.

    Supports:
    - Usernames: 'octocat' -> ('octocat', None)
    - Owner/Repo: 'octocat/Hello-World' -> ('octocat/Hello-World', None)
    - Ref syntax: 'octocat/Hello-World@dev' -> ('octocat/Hello-World', 'dev')
    - Tree URLs: 'https://github.com/octocat/Hello-World/tree/dev' -> ('octocat/Hello-World', 'dev')
    - Tree URLs with nested branch: 'https://github.com/octocat/Hello-World/tree/feature/login' -> ('octocat/Hello-World', 'feature/login')
    - SSH URLs: 'git@github.com:octocat/Hello-World.git' -> ('octocat/Hello-World', None)
    - SSH URLs with ref: 'git@github.com:octocat/Hello-World.git@dev' -> ('octocat/Hello-World', 'dev')
    """
    cleaned = target.strip()
    if not cleaned:
        return ("", None)

    branch: str | None = None

    # Handle SSH git URLs: git@github.com:owner/repo(.git)(@branch)
    if cleaned.startswith("git@github.com:"):
        remainder = cleaned[len("git@github.com:"):]
        if "@" in remainder:
            remainder, branch = remainder.split("@", 1)
            branch = branch.strip() or None
        return (normalize_target(remainder), branch)

    # Check for HTTP(S) URLs or github.com/ URLs with /tree/
    if "://" in cleaned or cleaned.startswith("github.com/"):
        parsed = urlparse(cleaned if "://" in cleaned else f"https://{cleaned}")
        path_segments = [p.strip() for p in parsed.path.lstrip("/").split("/") if p.strip()]
        if len(path_segments) >= 4 and path_segments[2] == "tree":
            owner = path_segments[0]
            repo = path_segments[1]
            if repo.endswith(".git"):
                repo = repo[:-4]
            branch = "/".join(path_segments[3:])
            return (f"{owner}/{repo}", branch or None)

    # Check for @branch syntax
    if "@" in cleaned:
        target_part, branch_part = cleaned.split("@", 1)
        return (normalize_target(target_part), branch_part.strip() or None)

    return (normalize_target(cleaned), None)


def normalize_target(target: str) -> str:
    """Normalize a GitHub username, repository, or URL into a standard target string.

    Supports:
    - Usernames: 'octocat' -> 'octocat'
    - Owner/Repo: 'octocat/Hello-World' -> 'octocat/Hello-World'
    - HTTPS/HTTP URLs: 'https://github.com/octocat/Hello-World' -> 'octocat/Hello-World'
    - Clone URLs with .git: 'https://github.com/octocat/Hello-World.git' -> 'octocat/Hello-World'
    - SSH URLs: 'git@github.com:octocat/Hello-World.git' -> 'octocat/Hello-World'
    - Tree/Blob/Deep URLs: 'https://github.com/octocat/Hello-World/tree/main' -> 'octocat/Hello-World'
    - User profile URLs: 'https://github.com/octocat' -> 'octocat'
    """
    cleaned = target.strip()
    if not cleaned:
        return cleaned

    # Handle SSH git URLs: git@github.com:owner/repo(.git)
    if cleaned.startswith("git@github.com:"):
        cleaned = cleaned[len("git@github.com:"):]
    elif cleaned.startswith("github.com/"):
        cleaned = cleaned[len("github.com/"):]
    elif "://" in cleaned:
        parsed = urlparse(cleaned)
        cleaned = parsed.path.lstrip("/")

    # Strip trailing .git if present
    if cleaned.endswith(".git"):
        cleaned = cleaned[:-4]

    # Split path components and strip empty elements
    parts = [p.strip() for p in cleaned.split("/") if p.strip()]
    if len(parts) >= 2:
        return f"{parts[0]}/{parts[1]}"
    elif len(parts) == 1:
        return parts[0]

    return cleaned


def main(argv: Sequence[str] | None = None) -> int:
    """Main CLI entry point."""
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.token == _USE_ENV_TOKEN:
        args.token = get_env_github_token()

    configure_logging(args.verbose)

    # Determine whether target is a single repo (owner/repo, URL, or --repo flag) or a user
    target_str, detected_branch = parse_target_ref(args.target)
    target_branch = args.branch if args.branch is not None else detected_branch

    if "/" in target_str:
        parts = target_str.split("/", 1)
        owner = parts[0].strip()
        repo_name = parts[1].strip()
        is_single_repo = True
    elif args.repo:
        owner = target_str
        cleaned_repo, repo_flag_branch = parse_target_ref(args.repo)
        if "/" in cleaned_repo:
            repo_name = cleaned_repo.split("/", 1)[1]
        else:
            repo_name = cleaned_repo
        if target_branch is None and repo_flag_branch:
            target_branch = repo_flag_branch
        is_single_repo = True
    else:
        owner = target_str
        repo_name = None
        is_single_repo = False

    if not is_single_repo and target_branch:
        sys.stderr.write("Error: --branch can only be used when scanning a single repository.\n")
        return 1

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
                    branch=target_branch,
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

        if stats is None:
            return 1

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

