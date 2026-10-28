"""GitHub REST API client with pagination, rate limiting, and error recovery."""

from __future__ import annotations

import base64
from dataclasses import dataclass
import logging
import os
import time
from typing import Any, Callable
import httpx

from repo_language_stats.discovery import TreeEntry

logger = logging.getLogger(__name__)

GITHUB_API_BASE_URL = "https://api.github.com"


@dataclass
class RepoInfo:
    """GitHub repository metadata."""

    name: str
    owner: str
    default_branch: str = "main"
    is_fork: bool = False
    is_private: bool = False
    size: int = 0
    description: str = ""

    @classmethod
    def from_api_dict(cls, data: dict[str, Any]) -> RepoInfo:
        owner_data = data.get("owner", {})
        owner_login = owner_data.get("login", "") if isinstance(owner_data, dict) else ""
        return cls(
            name=data.get("name", ""),
            owner=owner_login,
            default_branch=data.get("default_branch", "main"),
            is_fork=bool(data.get("fork", False)),
            is_private=bool(data.get("private", False)),
            size=int(data.get("size", 0)),
            description=data.get("description", "") or "",
        )


class GitHubAPIClient:
    """Client for GitHub REST API v3."""

    def __init__(
        self,
        token: str | None = None,
        base_url: str = GITHUB_API_BASE_URL,
        rate_limit_threshold: int = 10,
        max_retries: int = 3,
        retry_backoff_base: float = 2.0,
        sleep_func: Callable[[float], None] | None = None,
        client: httpx.Client | None = None,
    ) -> None:
        self.token = token or os.getenv("GITHUB_TOKEN")
        self.base_url = base_url.rstrip("/")
        self.rate_limit_threshold = rate_limit_threshold
        self.max_retries = max_retries
        self.retry_backoff_base = retry_backoff_base
        self._sleep = sleep_func or time.sleep

        headers = {
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "repo-language-stats",
        }
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"

        self._client = client or httpx.Client(
            base_url=self.base_url,
            headers=headers,
            timeout=30.0,
            follow_redirects=True,
        )

    def close(self) -> None:
        """Close the underlying HTTP client."""
        self._client.close()

    def __enter__(self) -> GitHubAPIClient:
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        self.close()

    def _check_rate_limit(self, response: httpx.Response) -> None:
        """Inspect response headers for rate limit thresholds."""
        remaining_hdr = response.headers.get("x-ratelimit-remaining")
        reset_hdr = response.headers.get("x-ratelimit-reset")

        if remaining_hdr is not None and reset_hdr is not None:
            try:
                rem = int(remaining_hdr)
                if rem <= self.rate_limit_threshold:
                    reset_ts = float(reset_hdr)
                    sleep_sec = max(0.0, reset_ts - time.time() + 1.0)
                    logger.warning(
                        "Rate limit remaining (%d) <= threshold (%d). Sleeping for %.1fs until reset.",
                        rem,
                        self.rate_limit_threshold,
                        sleep_sec,
                    )
                    self._sleep(sleep_sec)
            except (ValueError, TypeError):
                pass

    def _request(
        self,
        method: str,
        endpoint: str,
        params: dict[str, Any] | None = None,
    ) -> httpx.Response | None:
        """Execute an HTTP request with retries, backoff, and rate-limit handling.

        Returns None on 404 or 422 errors.
        """
        url = endpoint if endpoint.startswith("http") else f"{self.base_url}/{endpoint.lstrip('/')}"
        retries = 0

        while True:
            try:
                resp = self._client.request(method, url, params=params)

                # Check rate limit headers on any response
                self._check_rate_limit(resp)

                if resp.status_code == 200:
                    return resp

                if resp.status_code == 404:
                    logger.warning("Resource not found (404): %s", url)
                    return None

                if resp.status_code in (409, 422):
                    logger.info("Empty repository or unprocessable entity (%d): %s", resp.status_code, url)
                    return None

                if resp.status_code in (403, 429):
                    # Check for rate limit exhaustion or secondary rate limits
                    retry_after = resp.headers.get("retry-after")
                    if retry_after:
                        try:
                            sleep_sec = float(retry_after) + 1.0
                            logger.warning("Secondary rate limit hit (403/429). Sleeping %.1fs", sleep_sec)
                            self._sleep(sleep_sec)
                            continue
                        except (ValueError, TypeError):
                            pass

                    if resp.headers.get("x-ratelimit-remaining") == "0":
                        reset_hdr = resp.headers.get("x-ratelimit-reset")
                        if reset_hdr:
                            try:
                                sleep_sec = max(0.0, float(reset_hdr) - time.time() + 1.0)
                                logger.warning("Rate limit exhausted (403). Sleeping %.1fs until reset", sleep_sec)
                                self._sleep(sleep_sec)
                                continue
                            except (ValueError, TypeError):
                                pass

                    logger.warning("Access forbidden / denied (403): %s", url)
                    return None

                if resp.status_code >= 500:
                    retries += 1
                    if retries > self.max_retries:
                        logger.error("HTTP %d error after %d retries: %s", resp.status_code, self.max_retries, url)
                        return None
                    sleep_sec = self.retry_backoff_base ** retries
                    logger.warning("Server error %d. Retrying in %.1fs (%d/%d)...", resp.status_code, sleep_sec, retries, self.max_retries)
                    self._sleep(sleep_sec)
                    continue

                resp.raise_for_status()
                return resp

            except (httpx.RequestError, httpx.TimeoutException) as exc:
                retries += 1
                if retries > self.max_retries:
                    logger.error("Network error after %d retries for %s: %s", self.max_retries, url, exc)
                    raise
                sleep_sec = self.retry_backoff_base ** retries
                logger.warning("Network failure (%s). Retrying in %.1fs (%d/%d)...", exc, sleep_sec, retries, self.max_retries)
                self._sleep(sleep_sec)

    def list_repos(
        self,
        username: str,
        include_forks: bool = False,
    ) -> list[RepoInfo]:
        """List repositories for a given user, following pagination."""
        repos: list[RepoInfo] = []
        endpoint: str | None = f"users/{username}/repos"
        params: dict[str, Any] | None = {"per_page": 100}
        visited_urls: set[str] = set()

        while endpoint:
            if endpoint in visited_urls:
                break
            visited_urls.add(endpoint)

            resp = self._request("GET", endpoint, params=params)
            if not resp:
                break

            items = resp.json()
            if not isinstance(items, list):
                break

            for item in items:
                repo = RepoInfo.from_api_dict(item)
                if not include_forks and repo.is_fork:
                    continue
                repos.append(repo)

            # Check Link header for rel="next"
            endpoint = None
            params = None  # Next URL already includes params
            link_header = resp.headers.get("link", "")
            if link_header:
                links = link_header.split(",")
                for link in links:
                    parts = link.split(";")
                    if len(parts) >= 2 and 'rel="next"' in parts[1]:
                        endpoint = parts[0].strip().strip("<>")
                        break

        return repos

    def get_tree(
        self,
        owner: str,
        repo: str,
        sha: str = "HEAD",
    ) -> tuple[list[TreeEntry], bool]:
        """Retrieve the Git tree for a repository default branch.

        Returns (entries, is_truncated).
        """
        endpoint = f"repos/{owner}/{repo}/git/trees/{sha}"
        resp = self._request("GET", endpoint, params={"recursive": "1"})
        if not resp:
            return [], False

        data = resp.json()
        is_truncated = bool(data.get("truncated", False))
        if is_truncated:
            logger.warning("Repository tree for %s/%s was truncated (>100k files). Processing partial tree.", owner, repo)

        raw_tree = data.get("tree", [])
        entries = [TreeEntry.from_api_dict(item) for item in raw_tree if isinstance(item, dict)]
        return entries, is_truncated

    def get_blob(
        self,
        owner: str,
        repo: str,
        sha: str,
    ) -> bytes | None:
        """Retrieve and decode a blob from the Git Blobs API."""
        endpoint = f"repos/{owner}/{repo}/git/blobs/{sha}"
        resp = self._request("GET", endpoint)
        if not resp:
            return None

        data = resp.json()
        encoding = data.get("encoding", "")
        content_raw = data.get("content", "")

        if encoding == "base64":
            try:
                return base64.b64decode(content_raw)
            except Exception as exc:
                logger.warning("Failed to decode base64 blob %s: %s", sha, exc)
                return None
        elif isinstance(content_raw, str):
            return content_raw.encode("utf-8")
        elif isinstance(content_raw, bytes):
            return content_raw

        return None
