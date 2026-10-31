# Private Repository Scanning

This document describes how `repo-language-stats` will be extended to include private repositories in language statistics.

---

## 1. Current Behavior

Today, `repo-language-stats` lists repositories via the GitHub REST API endpoint:

```
GET /users/{username}/repos
```

This endpoint returns **only public repositories** regardless of whether a token is supplied. The current `GITHUB_TOKEN` is used solely to increase the API rate limit from 60 to 5,000 requests per hour — it does not unlock access to private repositories.

---

## 2. The Problem

Users who maintain significant codebases in private repositories get an incomplete picture of their language distribution. A developer whose private repos contain most of their Python and Go code but whose public repos are JavaScript-heavy will see skewed statistics that don't reflect their true language profile.

---

## 3. How GitHub's API Handles Private Repos

GitHub provides two different repo-listing endpoints relevant to this feature:

| Endpoint | Visibility | Auth Required | Notes |
|---|---|---|---|
| `GET /users/{username}/repos` | Public only | No (token optional for rate limits) | Current behavior. Works for any username. |
| `GET /user/repos` | Public + Private | Yes (authenticated user only) | Returns all repos the **authenticated user** owns or has access to. Cannot be used to list another user's private repos. |

**Key constraint**: You can only list your *own* private repos. GitHub does not allow listing another user's private repos, even with a token — that would be a security violation.

---

## 4. Proposed Implementation

### 4.1 New CLI Flag: `--include-private`

```
repo-language-stats WDWaleed --include-private
```

When `--include-private` is passed:

1. A `GITHUB_TOKEN` **must** be provided (via `--token` or the `GITHUB_TOKEN` environment variable). If no token is present, exit with a clear error message.
2. The tool verifies that the authenticated token belongs to the target username by calling `GET /user` and comparing the returned `login` field against the target. If they don't match, exit with an error explaining that private repo access is only available for the authenticated user's own account.
3. The repo listing switches from `GET /users/{username}/repos` to `GET /user/repos` with the query parameter `visibility=all` (or `type=owner` to exclude repos from organizations the user is a member of).

### 4.2 Changes to `github_api.py`

#### New Method: `get_authenticated_user()`

```python
def get_authenticated_user(self) -> str | None:
    """Return the login username of the currently authenticated token."""
    resp = self._request("GET", "user")
    if not resp:
        return None
    data = resp.json()
    return data.get("login")
```

#### Modified Method: `list_repos()`

Add an `include_private` parameter:

```python
def list_repos(
    self,
    username: str,
    include_forks: bool = False,
    include_private: bool = False,
) -> list[RepoInfo]:
    if include_private:
        # Use authenticated endpoint — returns public + private
        endpoint = "user/repos"
        params = {"per_page": 100, "type": "owner", "sort": "updated"}
    else:
        # Public-only endpoint (current behavior)
        endpoint = f"users/{username}/repos"
        params = {"per_page": 100}

    # ... rest of pagination logic unchanged ...
```

The `type=owner` parameter filters out repos where the user is only a collaborator or org member, keeping results scoped to repos the user actually owns.

### 4.3 Changes to `cli.py`

#### Parser Addition

```python
parser.add_argument(
    "--include-private",
    action="store_true",
    default=False,
    help="Include private repositories (requires a token with 'repo' scope; "
         "only works when scanning your own account).",
)
```

#### Validation in `main()`

Before scanning, when `--include-private` is set:

```python
if args.include_private:
    if not args.token:
        sys.stderr.write(
            "Error: --include-private requires a GitHub token. "
            "Set GITHUB_TOKEN or pass --token.\n"
        )
        return 1

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
```

### 4.4 Token Scope Requirements

The GitHub personal access token must have the following scope:

| Token Type | Required Scope | Grants |
|---|---|---|
| **Classic PAT** | `repo` | Full read/write to all repos (public + private). This is the broadest scope; GitHub does not offer a read-only classic scope for private repos. |
| **Fine-grained PAT** | Repository access: "All repositories" or select specific repos, with **Contents: Read** permission | Read-only access to repository contents. Preferred for security — no write access needed. |

> **Recommendation**: Use a **fine-grained PAT** with read-only Contents permission scoped to "All repositories". This follows the principle of least privilege — the tool only needs to read file trees and blob contents, never write.

### 4.5 Privacy Considerations

- **No private data leakage in output**: The tool must not change its output format in any way that reveals whether a repo is public or private. Language names, byte counts, and line counts are safe. Repo names appear in `--per-repo` output, so users should be aware that using `--per-repo --include-private` will display private repository names in the terminal or exported file.
- **No logging of private repo contents**: At `INFO` verbosity, log repo names only (already the case). At `DEBUG` verbosity, file paths within repos may be logged — this is acceptable since debug output is local-only.
- **Web version (future)**: If private repo scanning is added to the web dashboard, generated SVG cards should aggregate stats only — never expose individual private repo names or file paths in the card content or API responses.

---

## 5. Changes to `RepoInfo`

The existing `RepoInfo.is_private` field is already populated from the API response:

```python
is_private=bool(data.get("private", False))
```

This field is currently unused. With this feature, it can be used for:
- Logging: `logger.info("Scanning %s repo %s/%s...", "private" if repo.is_private else "public", ...)`
- Optional filtering: a future `--private-only` flag could scan exclusively private repos.

---

## 6. Edge Cases

| Scenario | Behavior |
|---|---|
| `--include-private` without a token | Exit with error: token required. |
| Token is valid but belongs to a different user | Exit with error: can only scan own account. |
| Token lacks `repo` scope (classic PAT) | `GET /user/repos` returns only public repos silently. Warn the user if 0 private repos are found and suggest checking token scopes. |
| Fine-grained PAT with limited repo access | Only repos the token has access to are returned. This is expected behavior — no warning needed. |
| User has no private repos | Works normally, equivalent to not passing `--include-private`. |
| Combined with `--repo` (single repo mode) | `--include-private` is not needed for single-repo mode — `GET /repos/{owner}/{repo}` already returns private repos if the token has access. Show a warning that the flag is redundant in this mode. |
| Combined with `--include-forks` | Both flags work independently. Private forked repos are included only if both flags are set. |

---

## 7. Testing Strategy

| Test | Description |
|---|---|
| Unit: `list_repos(include_private=True)` | Mock `GET /user/repos` with `type=owner` param → verify private repos appear in results. |
| Unit: `get_authenticated_user()` | Mock `GET /user` → verify login extraction. |
| Unit: token validation | Verify error path when token is missing, invalid, or belongs to a different user. |
| Unit: `--include-private` flag parsing | Verify `argparse` wiring and `dest` attribute. |
| Integration (manual): real private repos | Run against a test GitHub account with known private repos and verify byte/line counts include private repo content. |

---

## 8. Summary of File Changes

| File | Change |
|---|---|
| `src/repo_language_stats/github_api.py` | Add `get_authenticated_user()` method; add `include_private` param to `list_repos()` |
| `src/repo_language_stats/cli.py` | Add `--include-private` argument; add token and ownership validation logic |
| `tests/test_github_api.py` | Add tests for `get_authenticated_user()` and `list_repos(include_private=True)` |
| `tests/test_cli.py` | Add tests for `--include-private` flag validation and error paths |
| `README.md` | Document the `--include-private` flag in CLI Reference and Usage sections |
| `docs/future_features.md` | Mark feature as implemented (move from Planned to Done) |

