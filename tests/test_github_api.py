"""Tests for GitHub REST API client."""

import json
from pathlib import Path
from unittest.mock import MagicMock
import httpx
import pytest
import respx

from repo_language_stats.github_api import GitHubAPIClient, RepoInfo

FIXTURES_DIR = Path(__file__).parent / "fixtures" / "api_responses"


@pytest.fixture
def mock_sleep():
    return MagicMock()


@respx.mock
def test_list_repos_single_page():
    page_data = json.loads((FIXTURES_DIR / "repos_page1.json").read_text(encoding="utf-8"))
    respx.get("https://api.github.com/users/octocat/repos").mock(
        return_value=httpx.Response(200, json=page_data)
    )

    client = GitHubAPIClient()
    repos = client.list_repos("octocat")
    assert len(repos) == 1
    assert repos[0].name == "repo1"
    assert repos[0].owner == "octocat"
    assert repos[0].default_branch == "main"
    assert repos[0].is_fork is False
    client.close()


@respx.mock
def test_get_repo_success():
    respx.get("https://api.github.com/repos/octocat/my-repo").mock(
        return_value=httpx.Response(
            200,
            json={
                "name": "my-repo",
                "owner": {"login": "octocat"},
                "default_branch": "main",
                "fork": False,
                "private": False,
                "size": 120,
            },
        )
    )

    with GitHubAPIClient() as client:
        repo = client.get_repo("octocat", "my-repo")
        assert repo is not None
        assert repo.name == "my-repo"
        assert repo.owner == "octocat"
        assert repo.default_branch == "main"
        assert repo.is_fork is False


@respx.mock
def test_get_repo_not_found():
    respx.get("https://api.github.com/repos/octocat/nonexistent").mock(
        return_value=httpx.Response(404)
    )

    with GitHubAPIClient() as client:
        repo = client.get_repo("octocat", "nonexistent")
        assert repo is None


@respx.mock
def test_list_repos_pagination():
    page1 = json.loads((FIXTURES_DIR / "repos_page1.json").read_text(encoding="utf-8"))
    page2 = json.loads((FIXTURES_DIR / "repos_page2.json").read_text(encoding="utf-8"))
    page3 = json.loads((FIXTURES_DIR / "repos_last_page.json").read_text(encoding="utf-8"))

    respx.get("https://api.github.com/users/octocat/repos", params={"per_page": "100"}).mock(
        return_value=httpx.Response(
            200,
            json=page1,
            headers={"link": '<https://api.github.com/users/octocat/repos?page=2>; rel="next"'},
        )
    )
    respx.get("https://api.github.com/users/octocat/repos", params={"page": "2"}).mock(
        return_value=httpx.Response(
            200,
            json=page2,
            headers={"link": '<https://api.github.com/users/octocat/repos?page=3>; rel="next"'},
        )
    )
    respx.get("https://api.github.com/users/octocat/repos", params={"page": "3"}).mock(
        return_value=httpx.Response(200, json=page3)
    )

    with GitHubAPIClient() as client:
        repos = client.list_repos("octocat", include_forks=True)
        assert len(repos) == 3
        assert [r.name for r in repos] == ["repo1", "repo2-forked", "repo3"]


@respx.mock
def test_exclude_forks():
    page1 = json.loads((FIXTURES_DIR / "repos_page1.json").read_text(encoding="utf-8"))
    page2 = json.loads((FIXTURES_DIR / "repos_page2.json").read_text(encoding="utf-8"))

    respx.get("https://api.github.com/users/octocat/repos").mock(
        return_value=httpx.Response(
            200,
            json=page1 + page2,
        )
    )

    with GitHubAPIClient() as client:
        # Forked repos excluded by default
        repos = client.list_repos("octocat", include_forks=False)
        assert len(repos) == 1
        assert repos[0].name == "repo1"


@respx.mock
def test_include_forks():
    page1 = json.loads((FIXTURES_DIR / "repos_page1.json").read_text(encoding="utf-8"))
    page2 = json.loads((FIXTURES_DIR / "repos_page2.json").read_text(encoding="utf-8"))

    respx.get("https://api.github.com/users/octocat/repos").mock(
        return_value=httpx.Response(
            200,
            json=page1 + page2,
        )
    )

    with GitHubAPIClient() as client:
        repos = client.list_repos("octocat", include_forks=True)
        assert len(repos) == 2
        assert repos[1].name == "repo2-forked"
        assert repos[1].is_fork is True


@respx.mock
def test_get_tree_recursive():
    tree_data = json.loads((FIXTURES_DIR / "tree_response.json").read_text(encoding="utf-8"))
    respx.get("https://api.github.com/repos/octocat/repo1/git/trees/main").mock(
        return_value=httpx.Response(200, json=tree_data)
    )

    with GitHubAPIClient() as client:
        entries, is_truncated = client.get_tree("octocat", "repo1", sha="main")
        assert is_truncated is False
        assert len(entries) == 2
        assert entries[0].path == "src/main.py"
        assert entries[0].type == "blob"
        assert entries[1].path == "src"
        assert entries[1].type == "tree"


@respx.mock
def test_get_tree_truncated(caplog):
    tree_data = json.loads((FIXTURES_DIR / "tree_truncated.json").read_text(encoding="utf-8"))
    respx.get("https://api.github.com/repos/octocat/repo1/git/trees/main").mock(
        return_value=httpx.Response(200, json=tree_data)
    )

    with caplog.at_level("WARNING"):
        with GitHubAPIClient() as client:
            entries, is_truncated = client.get_tree("octocat", "repo1", sha="main")
            assert is_truncated is True
            assert len(entries) == 1
            assert entries[0].path == "file1.py"
            assert "was truncated" in caplog.text


@respx.mock
def test_get_blob_base64():
    blob_data = json.loads((FIXTURES_DIR / "blob_response.json").read_text(encoding="utf-8"))
    respx.get("https://api.github.com/repos/octocat/repo1/git/blobs/blob1").mock(
        return_value=httpx.Response(200, json=blob_data)
    )

    with GitHubAPIClient() as client:
        content = client.get_blob("octocat", "repo1", "blob1")
        assert content is not None
        assert content.decode("utf-8") == 'print("hello")\n'


@respx.mock
def test_rate_limit_sleep(mock_sleep):
    tree_data = json.loads((FIXTURES_DIR / "tree_response.json").read_text(encoding="utf-8"))
    # Header indicates remaining requests is below threshold (5 <= 10)
    respx.get("https://api.github.com/repos/octocat/repo1/git/trees/main").mock(
        return_value=httpx.Response(
            200,
            json=tree_data,
            headers={
                "x-ratelimit-remaining": "5",
                "x-ratelimit-reset": "1800000000",
            },
        )
    )

    with GitHubAPIClient(sleep_func=mock_sleep, rate_limit_threshold=10) as client:
        client.get_tree("octocat", "repo1", "main")
        assert mock_sleep.called
        # Verify sleep duration is > 0
        sleep_arg = mock_sleep.call_args[0][0]
        assert sleep_arg > 0


@respx.mock
def test_retry_on_5xx(mock_sleep):
    route = respx.get("https://api.github.com/repos/octocat/repo1/git/blobs/blob1")
    # First returns 500, then returns 200
    route.side_effect = [
        httpx.Response(500),
        httpx.Response(200, json={"encoding": "base64", "content": "cHJpbnQoMSk="}),
    ]

    with GitHubAPIClient(sleep_func=mock_sleep, retry_backoff_base=1.0) as client:
        content = client.get_blob("octocat", "repo1", "blob1")
        assert content == b"print(1)"
        assert mock_sleep.called


@respx.mock
def test_skip_on_404(caplog):
    respx.get("https://api.github.com/repos/octocat/missing/git/trees/main").mock(
        return_value=httpx.Response(404)
    )

    with caplog.at_level("WARNING"):
        with GitHubAPIClient() as client:
            entries, is_truncated = client.get_tree("octocat", "missing", "main")
            assert entries == []
            assert is_truncated is False
            assert "Resource not found (404)" in caplog.text


@respx.mock
def test_skip_on_422_empty_repo(caplog):
    respx.get("https://api.github.com/repos/octocat/empty/git/trees/main").mock(
        return_value=httpx.Response(422)
    )

    with caplog.at_level("INFO"):
        with GitHubAPIClient() as client:
            entries, is_truncated = client.get_tree("octocat", "empty", "main")
            assert entries == []
            assert "Empty repository or unprocessable entity (422)" in caplog.text


@respx.mock
def test_skip_on_409_empty_repo(caplog):
    respx.get("https://api.github.com/repos/octocat/conflict-empty/git/trees/main").mock(
        return_value=httpx.Response(409, json={"message": "Git Repository is empty."})
    )

    with caplog.at_level("INFO"):
        with GitHubAPIClient() as client:
            entries, is_truncated = client.get_tree("octocat", "conflict-empty", "main")
            assert entries == []
            assert is_truncated is False
            assert "Empty repository or unprocessable entity (409)" in caplog.text


@respx.mock
def test_auth_header_sent():
    route = respx.get("https://api.github.com/users/octocat/repos").mock(
        return_value=httpx.Response(200, json=[])
    )

    with GitHubAPIClient(token="secret_token_123") as client:
        client.list_repos("octocat")
        assert route.called
        auth_hdr = route.calls.last.request.headers.get("authorization")
        assert auth_hdr == "Bearer secret_token_123"


@respx.mock
def test_secondary_rate_limit_retry_after(mock_sleep):
    route = respx.get("https://api.github.com/repos/octocat/repo1/git/blobs/b1")
    route.side_effect = [
        httpx.Response(403, headers={"retry-after": "5"}),
        httpx.Response(200, json={"encoding": "base64", "content": "YWJj"}),
    ]

    with GitHubAPIClient(sleep_func=mock_sleep) as client:
        res = client.get_blob("octocat", "repo1", "b1")
        assert res == b"abc"
        assert mock_sleep.called
        assert mock_sleep.call_args[0][0] == 6.0  # 5 + 1.0 buffer


@respx.mock
def test_rate_limit_zero_remaining_403(mock_sleep):
    route = respx.get("https://api.github.com/repos/octocat/repo1/git/blobs/b2")
    route.side_effect = [
        httpx.Response(403, headers={"x-ratelimit-remaining": "0", "x-ratelimit-reset": "1800000000"}),
        httpx.Response(200, json={"encoding": "base64", "content": "YWJj"}),
    ]

    with GitHubAPIClient(sleep_func=mock_sleep) as client:
        res = client.get_blob("octocat", "repo1", "b2")
        assert res == b"abc"
        assert mock_sleep.called


@respx.mock
def test_forbidden_403_access_denied(caplog):
    respx.get("https://api.github.com/repos/octocat/secret/git/trees/main").mock(
        return_value=httpx.Response(403)
    )

    with caplog.at_level("WARNING"):
        with GitHubAPIClient() as client:
            entries, is_trunc = client.get_tree("octocat", "secret", "main")
            assert entries == []
            assert "Access forbidden / denied (403)" in caplog.text


@respx.mock
def test_server_error_max_retries_exceeded(mock_sleep, caplog):
    respx.get("https://api.github.com/repos/octocat/repo1/git/blobs/b3").mock(
        return_value=httpx.Response(500)
    )

    with caplog.at_level("ERROR"):
        with GitHubAPIClient(sleep_func=mock_sleep, max_retries=2, retry_backoff_base=1.0) as client:
            res = client.get_blob("octocat", "repo1", "b3")
            assert res is None
            assert "HTTP 500 error after 2 retries" in caplog.text


@respx.mock
def test_network_error_retry_and_exhaustion(mock_sleep, caplog):
    respx.get("https://api.github.com/repos/octocat/repo1/git/blobs/b4").mock(
        side_effect=httpx.ConnectError("Connection refused")
    )

    with pytest.raises(httpx.ConnectError):
        with GitHubAPIClient(sleep_func=mock_sleep, max_retries=2, retry_backoff_base=1.0) as client:
            client.get_blob("octocat", "repo1", "b4")


@respx.mock
def test_blob_formats_and_invalid_base64(caplog):
    # Raw string content
    respx.get("https://api.github.com/repos/octocat/repo1/git/blobs/str").mock(
        return_value=httpx.Response(200, json={"encoding": "utf-8", "content": "raw string content"})
    )
    # Corrupted base64
    respx.get("https://api.github.com/repos/octocat/repo1/git/blobs/corrupt").mock(
        return_value=httpx.Response(200, json={"encoding": "base64", "content": "???not-base64???"})
    )

    with GitHubAPIClient() as client:
        res_str = client.get_blob("octocat", "repo1", "str")
        assert res_str == b"raw string content"

        with caplog.at_level("WARNING"):
            res_bad = client.get_blob("octocat", "repo1", "corrupt")
            assert res_bad is None
            assert "Failed to decode base64 blob" in caplog.text


@respx.mock
def test_get_authenticated_user_success():
    respx.get("https://api.github.com/user").mock(
        return_value=httpx.Response(200, json={"login": "WDWaleed", "id": 12345})
    )

    with GitHubAPIClient(token="ghp_test_token") as client:
        user = client.get_authenticated_user()
        assert user == "WDWaleed"


@respx.mock
def test_get_authenticated_user_unauthorized():
    respx.get("https://api.github.com/user").mock(
        return_value=httpx.Response(401, json={"message": "Bad credentials"})
    )

    with GitHubAPIClient(token="ghp_invalid") as client:
        user = client.get_authenticated_user()
        assert user is None


@respx.mock
def test_get_authenticated_user_empty_or_malformed():
    respx.get("https://api.github.com/user").mock(
        return_value=httpx.Response(200, json={})
    )

    with GitHubAPIClient(token="ghp_test_token") as client:
        user = client.get_authenticated_user()
        assert user is None


@respx.mock
def test_list_repos_include_private():
    respx.get(
        "https://api.github.com/user/repos",
        params={"per_page": "100", "type": "owner", "sort": "updated"},
    ).mock(
        return_value=httpx.Response(
            200,
            json=[
                {
                    "name": "public-repo",
                    "owner": {"login": "WDWaleed"},
                    "default_branch": "main",
                    "fork": False,
                    "private": False,
                },
                {
                    "name": "private-repo",
                    "owner": {"login": "WDWaleed"},
                    "default_branch": "main",
                    "fork": False,
                    "private": True,
                },
                {
                    "name": "private-fork",
                    "owner": {"login": "WDWaleed"},
                    "default_branch": "main",
                    "fork": True,
                    "private": True,
                },
            ],
        )
    )

    with GitHubAPIClient(token="ghp_test_token") as client:
        # include_forks=False (default)
        repos = client.list_repos("WDWaleed", include_forks=False, include_private=True)
        assert len(repos) == 2
        assert repos[0].name == "public-repo"
        assert repos[0].is_private is False
        assert repos[1].name == "private-repo"
        assert repos[1].is_private is True

        # include_forks=True
        all_repos = client.list_repos("WDWaleed", include_forks=True, include_private=True)
        assert len(all_repos) == 3
        assert [r.name for r in all_repos] == ["public-repo", "private-repo", "private-fork"]

