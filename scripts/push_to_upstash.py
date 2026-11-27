#!/usr/bin/env python3
"""Push aggregated language statistics to Upstash Redis.

Usage:
    uv run scripts/push_to_upstash.py --username WDWaleed [--stats-file stats.json]
    uv run scripts/push_to_upstash.py --username WDWaleed --dry-run

Reads UPSTASH_REDIS_REST_URL and UPSTASH_REDIS_REST_TOKEN from the
environment (or .env file in the project root).

Key convention (Decision D5):
    stats:{username}   — CachedUserStats JSON payload
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# Dependency: httpx (already in project via other optional deps or fallback)
# ---------------------------------------------------------------------------
try:
    import httpx
except ImportError:
    sys.stderr.write(
        "Error: 'httpx' is required. Install it with: uv add httpx\n"
    )
    sys.exit(1)

logger = logging.getLogger("push_to_upstash")


# ---------------------------------------------------------------------------
# .env loader (minimal — no extra dependencies)
# ---------------------------------------------------------------------------

def _load_env_file(env_path: Path) -> None:
    """Load key=value pairs from an .env file into os.environ (non-clobbering)."""
    if not env_path.is_file():
        return
    with open(env_path, encoding="utf-8") as fh:
        for raw_line in fh:
            line = raw_line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            if line.startswith("export "):
                line = line[7:].strip()
            key, _, value = line.partition("=")
            key = key.strip()
            value = value.strip().strip('"').strip("'")
            if key and key not in os.environ:
                os.environ[key] = value


# ---------------------------------------------------------------------------
# Payload builder
# ---------------------------------------------------------------------------

def build_payload(
    username: str,
    stats: dict[str, Any],
    inject_colors: bool = True,
) -> dict[str, Any]:
    """Build the CachedUserStats payload from a raw stats dict.

    Injects Linguist hex color codes into each language entry so the
    frontend can render cards without an extra lookup (Decision D5).

    Args:
        username:       GitHub username.
        stats:          Dict from stats.json (AggregateStats-shaped).
        inject_colors:  When True, resolve and inject Linguist colors.

    Returns:
        A dict matching the CachedUserStats TypeScript interface.
    """
    # Resolve color injector lazily (avoid import cost on dry-runs)
    color_fn = None
    if inject_colors:
        from repo_language_stats.svg.utils import resolve_language_color
        color_fn = resolve_language_color

    # Normalise language list from either dict or list form
    raw_aggregate: dict[str, Any] = stats.get("aggregate", {})
    raw_languages_list: list[dict[str, Any]] = stats.get("languages", [])

    if raw_aggregate:
        languages_input = [
            {
                "language": lang_name,
                "bytes": int(info.get("total_bytes", 0)),
                "lines": int(info.get("total_lines", 0)),
                "files": int(info.get("file_count", 0)),
            }
            for lang_name, info in raw_aggregate.items()
        ]
    else:
        languages_input = [
            {
                "language": str(item.get("language", "")),
                "bytes": int(item.get("bytes", item.get("total_bytes", 0))),
                "lines": int(item.get("lines", item.get("total_lines", 0))),
                "files": int(item.get("files", item.get("file_count", 0))),
                "color": item.get("color"),
            }
            for item in raw_languages_list
        ]

    total_bytes: int = int(stats.get("total_bytes", sum(l["bytes"] for l in languages_input)))
    total_lines: int = int(stats.get("total_lines", sum(l["lines"] for l in languages_input)))

    # Sort descending by bytes
    languages_input.sort(key=lambda x: x["bytes"], reverse=True)

    languages_out: list[dict[str, Any]] = []
    for lang in languages_input:
        lang_name = lang["language"]
        b = lang["bytes"]
        l = lang["lines"]
        f = lang["files"]
        byte_pct = round((b / total_bytes * 100.0) if total_bytes > 0 else 0.0, 2)
        line_pct = round((l / total_lines * 100.0) if total_lines > 0 else 0.0, 2)

        entry: dict[str, Any] = {
            "language": lang_name,
            "bytes": b,
            "byte_percent": byte_pct,
            "lines": l,
            "line_percent": line_pct,
            "files": f,
        }

        # Inject color: use pre-existing color if already in input, else resolve
        existing_color: str | None = lang.get("color")
        if inject_colors and color_fn is not None:
            entry["color"] = existing_color or color_fn(lang_name)
        elif existing_color:
            entry["color"] = existing_color

        languages_out.append(entry)

    payload: dict[str, Any] = {
        "username": username,
        "repos_scanned": int(stats.get("repos_scanned", 0)),
        "repos_skipped": int(stats.get("repos_skipped", 0)),
        "total_bytes": total_bytes,
        "total_lines": total_lines,
        "languages": languages_out,
        "last_scanned": datetime.now(timezone.utc).isoformat(),
    }
    return payload


# ---------------------------------------------------------------------------
# Upstash REST client
# ---------------------------------------------------------------------------

class UpstashClient:
    """Thin synchronous wrapper around Upstash Redis REST API."""

    def __init__(self, url: str, token: str, timeout: float = 10.0, retries: int = 3) -> None:
        self._url = url.rstrip("/")
        self._headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        }
        self._timeout = timeout
        self._retries = retries

    def set(
        self,
        key: str,
        value: str,
        ex: int | None = None,
        retries: int | None = None,
        backoff: float = 1.5,
    ) -> dict[str, Any]:
        """Execute SET key value [EX seconds] with exponential-backoff retry."""
        effective_retries = self._retries if retries is None else retries
        cmd: list[str | int] = ["SET", key, value]
        if ex is not None:
            cmd += ["EX", ex]

        last_exc: Exception | None = None
        for attempt in range(1, effective_retries + 1):
            try:
                resp = httpx.post(
                    self._url,
                    headers=self._headers,
                    content=json.dumps(cmd),
                    timeout=self._timeout,
                )
                resp.raise_for_status()
                body = resp.json()
                if body.get("error"):
                    raise RuntimeError(f"Upstash error: {body['error']}")
                return body
            except (httpx.HTTPStatusError, httpx.RequestError, RuntimeError) as exc:
                last_exc = exc
                if attempt < effective_retries:
                    wait = backoff ** attempt
                    logger.warning(
                        "Attempt %d/%d failed (%s). Retrying in %.1fs…",
                        attempt, effective_retries, exc, wait,
                    )
                    time.sleep(wait)

        raise RuntimeError(f"All {effective_retries} attempts failed: {last_exc}") from last_exc

    def get(self, key: str) -> dict[str, Any]:
        """Execute GET key."""
        resp = httpx.post(
            self._url,
            headers=self._headers,
            content=json.dumps(["GET", key]),
            timeout=self._timeout,
        )
        resp.raise_for_status()
        return resp.json()


# ---------------------------------------------------------------------------
# Main sync logic
# ---------------------------------------------------------------------------

def sync_to_upstash(
    username: str,
    stats: dict[str, Any],
    client: UpstashClient,
    dry_run: bool = False,
    inject_colors: bool = True,
) -> dict[str, Any]:
    """Build payload and push to Redis under key `stats:{username}`.

    Returns the payload dict (useful for testing and dry-runs).
    """
    payload = build_payload(username, stats, inject_colors=inject_colors)
    key = f"stats:{username}"

    if dry_run:
        logger.info("[DRY RUN] Would SET %s (%d languages)", key, len(payload["languages"]))
        return payload

    result = client.set(key, json.dumps(payload, separators=(",", ":")))
    logger.info(
        "Synced %s → %s  (%d languages, %d bytes total).  Upstash result: %s",
        username, key, len(payload["languages"]), payload["total_bytes"], result,
    )
    return payload


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

def _build_arg_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="push_to_upstash",
        description="Push repo-language-stats AggregateStats JSON to Upstash Redis.",
    )
    p.add_argument(
        "--username", "-u",
        required=True,
        help="GitHub username whose stats are being pushed.",
    )
    p.add_argument(
        "--stats-file", "-f",
        type=Path,
        default=None,
        metavar="PATH",
        help=(
            "Path to a JSON file containing stats. "
            "If omitted, reads from stdin or runs rls scan on the fly."
        ),
    )
    p.add_argument(
        "--dry-run",
        action="store_true",
        default=False,
        help="Build the payload and print it, but do not push to Upstash.",
    )
    p.add_argument(
        "--no-color-inject",
        action="store_true",
        default=False,
        help="Disable Linguist color injection into the payload.",
    )
    p.add_argument(
        "--env-file",
        type=Path,
        default=Path(__file__).resolve().parent.parent / ".env",
        metavar="PATH",
        help="Path to .env file (default: project root .env).",
    )
    p.add_argument(
        "--retries",
        type=int,
        default=3,
        metavar="N",
        help="Number of retry attempts on transient errors (default: 3).",
    )
    p.add_argument(
        "-v", "--verbose",
        action="store_true",
        default=False,
        help="Enable verbose logging.",
    )
    return p


def main(argv: list[str] | None = None) -> int:
    args = _build_arg_parser().parse_args(argv)

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s  %(levelname)-8s  %(message)s",
        datefmt="%H:%M:%S",
    )

    # Load .env
    _load_env_file(args.env_file)

    url = os.environ.get("UPSTASH_REDIS_REST_URL", "").strip()
    token = os.environ.get("UPSTASH_REDIS_REST_TOKEN", "").strip()

    if not args.dry_run:
        if not url:
            sys.stderr.write(
                "Error: UPSTASH_REDIS_REST_URL is not set. "
                "Add it to .env or export it.\n"
            )
            return 1
        if not token:
            sys.stderr.write(
                "Error: UPSTASH_REDIS_REST_TOKEN is not set. "
                "Add it to .env or export it.\n"
            )
            return 1

    # Load stats
    if args.stats_file is not None:
        stats_path = args.stats_file
        if not stats_path.is_file():
            sys.stderr.write(f"Error: stats file not found: {stats_path}\n")
            return 1
        stats: dict[str, Any] = json.loads(stats_path.read_text(encoding="utf-8"))
    elif not sys.stdin.isatty():
        stats = json.load(sys.stdin)
    else:
        sys.stderr.write(
            "Error: provide --stats-file or pipe JSON via stdin.\n"
        )
        return 1

    client = UpstashClient(url=url or "http://localhost", token=token or "", retries=args.retries)

    try:
        payload = sync_to_upstash(
            username=args.username,
            stats=stats,
            client=client,
            dry_run=args.dry_run,
            inject_colors=not args.no_color_inject,
        )
    except Exception as exc:
        sys.stderr.write(f"Error: {exc}\n")
        logger.debug("", exc_info=True)
        return 1

    if args.dry_run:
        print(json.dumps(payload, indent=2))

    return 0


if __name__ == "__main__":
    sys.exit(main())
