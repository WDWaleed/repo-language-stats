"""Tests for CLI parsing, reporting formats, and end-to-end integration."""

import base64
import json
import logging
from pathlib import Path
import httpx
import pytest
import respx

from repo_language_stats.cli import build_parser, configure_logging, main
from repo_language_stats.counting import (
    AggregateStats,
    LanguageStats,
    RepoStats,
)
from repo_language_stats.reporting import (
    display_report,
    format_csv,
    format_json,
    format_table,
    print_table,
    render_report,
)

FIXTURES_DIR = Path(__file__).parent / "fixtures"


@pytest.fixture
def sample_stats() -> AggregateStats:
    """Fixture providing populated AggregateStats for testing formatters."""
    p1 = LanguageStats(language="Python", total_bytes=245120, total_lines=6230, file_count=89)
    js = LanguageStats(language="JavaScript", total_bytes=128450, total_lines=3102, file_count=45)
    nb = LanguageStats(language="Jupyter (Python)", total_bytes=31200, total_lines=410, file_count=5)

    repo1 = RepoStats(repo_name="repo-alpha", languages={"Python": p1, "JavaScript": js})
    repo2 = RepoStats(repo_name="repo-beta", languages={"Jupyter (Python)": nb})

    return AggregateStats(
        username="octocat",
        repos_scanned=2,
        repos_skipped=1,
        per_repo=[repo1, repo2],
        aggregate={
            "Python": LanguageStats("Python", 245120, 6230, 89),
            "JavaScript": LanguageStats("JavaScript", 128450, 3102, 45),
            "Jupyter (Python)": LanguageStats("Jupyter (Python)", 31200, 410, 5),
        },
        total_bytes=404770,
        total_lines=9742,
    )


def test_table_output(sample_stats: AggregateStats):
    output = format_table(sample_stats, per_repo=False, show_files=False)
    assert "GitHub Language Statistics for: octocat" in output
    assert "Repositories scanned: 2 │ Skipped: 1" in output
    assert "Python" in output
    assert "245,120" in output
    assert "JavaScript" in output
    assert "Jupyter (Python)" in output
    assert "TOTAL" in output
    assert "404,770" in output


def test_table_output_with_files(sample_stats: AggregateStats):
    output = format_table(sample_stats, per_repo=False, show_files=True)
    assert "Files" in output
    assert "89" in output
    assert "139" in output  # 89 + 45 + 5


def test_json_output(sample_stats: AggregateStats):
    json_str = format_json(sample_stats, per_repo=False, show_files=True)
    data = json.loads(json_str)

    assert data["username"] == "octocat"
    assert data["repos_scanned"] == 2
    assert data["repos_skipped"] == 1
    assert data["total_bytes"] == 404770
    assert len(data["languages"]) == 3

    top_lang = data["languages"][0]
    assert top_lang["language"] == "Python"
    assert top_lang["bytes"] == 245120
    assert top_lang["lines"] == 6230
    assert top_lang["files"] == 89
    assert "byte_percent" in top_lang
    assert "line_percent" in top_lang


def test_csv_output(sample_stats: AggregateStats):
    csv_str = format_csv(sample_stats, per_repo=False, show_files=True)
    lines = csv_str.strip().split("\n")

    assert lines[0] == "language,bytes,byte_percent,lines,line_percent,files"
    assert lines[1].startswith("Python,245120,")


def test_per_repo_output(sample_stats: AggregateStats):
    # Table mode with per-repo
    table_str = format_table(sample_stats, per_repo=True, show_files=False)
    assert "Repository: repo-alpha" in table_str
    assert "Repository: repo-beta" in table_str
    assert "Aggregate Summary" in table_str

    # JSON mode with per-repo
    json_str = format_json(sample_stats, per_repo=True, show_files=False)
    data = json.loads(json_str)
    assert "per_repo" in data
    assert len(data["per_repo"]) == 2
    assert data["per_repo"][0]["repo_name"] == "repo-alpha"

    # CSV mode with per-repo
    csv_str = format_csv(sample_stats, per_repo=True, show_files=False)
    assert csv_str.startswith("repository,language,bytes,byte_percent,lines,line_percent")
    assert "repo-alpha,Python," in csv_str


def test_render_report_dispatch(sample_stats: AggregateStats):
    assert "{" in render_report(sample_stats, fmt="json")
    assert "language,bytes" in render_report(sample_stats, fmt="csv")
    assert "Language" in render_report(sample_stats, fmt="table")


def test_missing_username():
    parser = build_parser()
    with pytest.raises(SystemExit):
        parser.parse_args([])


def test_verbose_flag(caplog):
    configure_logging(1)
    logger = logging.getLogger("repo_language_stats")
    with caplog.at_level(logging.INFO):
        logger.info("Test info log")
    assert "Test info log" in caplog.text

    configure_logging(2)
    with caplog.at_level(logging.DEBUG):
        logger.debug("Test debug log")
    assert "Test debug log" in caplog.text


def test_output_to_file(tmp_path: Path, sample_stats: AggregateStats):
    output_file = tmp_path / "stats.json"
    content = format_json(sample_stats)
    output_file.write_text(content, encoding="utf-8")

    assert output_file.exists()
    assert json.loads(output_file.read_text(encoding="utf-8"))["username"] == "octocat"


@respx.mock
def test_cli_end_to_end_table(capsys):
    # Mock repos list
    respx.get("https://api.github.com/users/octocat/repos", params={"per_page": "100"}).mock(
        return_value=httpx.Response(
            200,
            json=[
                {
                    "name": "sample-repo",
                    "owner": {"login": "octocat"},
                    "default_branch": "main",
                    "fork": False,
                    "size": 50,
                }
            ],
        )
    )

    # Mock tree
    respx.get("https://api.github.com/repos/octocat/sample-repo/git/trees/main", params={"recursive": "1"}).mock(
        return_value=httpx.Response(
            200,
            json={
                "truncated": False,
                "tree": [
                    {
                        "path": "main.py",
                        "mode": "100644",
                        "type": "blob",
                        "sha": "blob_py",
                        "size": 25,
                    },
                    {
                        "path": "notebook.ipynb",
                        "mode": "100644",
                        "type": "blob",
                        "sha": "blob_nb",
                        "size": 150,
                    },
                ],
            },
        )
    )

    # Mock blobs
    respx.get("https://api.github.com/repos/octocat/sample-repo/git/blobs/blob_py").mock(
        return_value=httpx.Response(
            200,
            json={"encoding": "base64", "content": base64.b64encode(b"print('hello world')\n").decode()},
        )
    )

    sample_nb_bytes = (FIXTURES_DIR / "sample.ipynb").read_bytes()
    respx.get("https://api.github.com/repos/octocat/sample-repo/git/blobs/blob_nb").mock(
        return_value=httpx.Response(
            200,
            json={"encoding": "base64", "content": base64.b64encode(sample_nb_bytes).decode()},
        )
    )

    ret = main(["octocat"])
    assert ret == 0

    captured = capsys.readouterr()
    assert "GitHub Language Statistics for: octocat" in captured.out
    assert "Python" in captured.out
    # Python and Jupyter (Python) are counted together under Python
    assert "Jupyter (Python)" not in captured.out
    # Ensure header only appears ONCE, not twice
    assert captured.out.count("GitHub Language Statistics for: octocat") == 1
    assert captured.out.count("Repositories scanned: 1 │ Skipped: 0") == 1


def test_display_report_json_csv_and_table(sample_stats: AggregateStats, capsys):
    display_report(sample_stats, fmt="json")
    captured = capsys.readouterr()
    assert captured.out.startswith("{")

    display_report(sample_stats, fmt="csv")
    captured = capsys.readouterr()
    assert captured.out.startswith("language,bytes")

    display_report(sample_stats, fmt="table")
    captured = capsys.readouterr()
    assert "GitHub Language Statistics for: octocat" in captured.out
    assert captured.out.count("GitHub Language Statistics for: octocat") == 1


@respx.mock
def test_cli_end_to_end_json_to_file(tmp_path: Path):
    respx.get("https://api.github.com/users/octocat/repos", params={"per_page": "100"}).mock(
        return_value=httpx.Response(
            200,
            json=[
                {
                    "name": "sample-repo",
                    "owner": {"login": "octocat"},
                    "default_branch": "main",
                    "fork": False,
                }
            ],
        )
    )

    respx.get("https://api.github.com/repos/octocat/sample-repo/git/trees/main", params={"recursive": "1"}).mock(
        return_value=httpx.Response(
            200,
            json={
                "truncated": False,
                "tree": [
                    {
                        "path": "main.py",
                        "type": "blob",
                        "sha": "blob_py",
                    }
                ],
            },
        )
    )

    respx.get("https://api.github.com/repos/octocat/sample-repo/git/blobs/blob_py").mock(
        return_value=httpx.Response(
            200,
            json={"encoding": "base64", "content": base64.b64encode(b"x = 10\n").decode()},
        )
    )

    out_file = tmp_path / "result.json"
    ret = main(["octocat", "--format", "json", "-o", str(out_file), "--show-files"])
    assert ret == 0

    assert out_file.exists()
    data = json.loads(out_file.read_text(encoding="utf-8"))
    assert data["username"] == "octocat"
    assert data["languages"][0]["language"] == "Python"
    assert data["languages"][0]["files"] == 1


@respx.mock
def test_cli_no_repos_found(capsys):
    respx.get("https://api.github.com/users/empty_user/repos", params={"per_page": "100"}).mock(
        return_value=httpx.Response(200, json=[])
    )

    ret = main(["empty_user", "--format", "json"])
    assert ret == 0

    captured = capsys.readouterr()
    data = json.loads(captured.out)
    assert data["username"] == "empty_user"
    assert data["repos_scanned"] == 0
    assert data["languages"] == []


@respx.mock
def test_cli_all_flag_includes_default_excluded(capsys):
    respx.get("https://api.github.com/users/octocat/repos", params={"per_page": "100"}).mock(
        return_value=httpx.Response(
            200,
            json=[
                {
                    "name": "sample-repo",
                    "owner": {"login": "octocat"},
                    "default_branch": "main",
                    "fork": False,
                }
            ],
        )
    )

    respx.get("https://api.github.com/repos/octocat/sample-repo/git/trees/main", params={"recursive": "1"}).mock(
        return_value=httpx.Response(
            200,
            json={
                "truncated": False,
                "tree": [
                    {
                        "path": "data.csv",
                        "type": "blob",
                        "sha": "blob_csv",
                    },
                    {
                        "path": "app.tsx",
                        "type": "blob",
                        "sha": "blob_tsx",
                    },
                ],
            },
        )
    )

    respx.get("https://api.github.com/repos/octocat/sample-repo/git/blobs/blob_csv").mock(
        return_value=httpx.Response(
            200,
            json={"encoding": "base64", "content": base64.b64encode(b"a,b,c\n1,2,3\n").decode()},
        )
    )
    respx.get("https://api.github.com/repos/octocat/sample-repo/git/blobs/blob_tsx").mock(
        return_value=httpx.Response(
            200,
            json={"encoding": "base64", "content": base64.b64encode(b"const x: number = 1;\n").decode()},
        )
    )

    # Without --all: data.csv should be excluded
    ret = main(["octocat", "--format", "json"])
    assert ret == 0
    captured = capsys.readouterr()
    data = json.loads(captured.out)
    langs = [item["language"] for item in data["languages"]]
    assert "CSV" not in langs
    # app.tsx should be counted as TypeScript
    assert "TypeScript" in langs
    assert "TSX" not in langs

    # With --all: data.csv should be included
    ret_all = main(["octocat", "--format", "json", "--all"])
    assert ret_all == 0
    captured_all = capsys.readouterr()
    data_all = json.loads(captured_all.out)
    langs_all = [item["language"] for item in data_all["languages"]]
    assert "CSV" in langs_all
    assert "TypeScript" in langs_all


@respx.mock
def test_cli_single_repo_slash_syntax(capsys):
    respx.get("https://api.github.com/repos/octocat/single-repo").mock(
        return_value=httpx.Response(
            200,
            json={
                "name": "single-repo",
                "owner": {"login": "octocat"},
                "default_branch": "main",
                "fork": False,
            },
        )
    )

    respx.get("https://api.github.com/repos/octocat/single-repo/git/trees/main", params={"recursive": "1"}).mock(
        return_value=httpx.Response(
            200,
            json={
                "truncated": False,
                "tree": [
                    {
                        "path": "index.js",
                        "type": "blob",
                        "sha": "blob_js",
                    }
                ],
            },
        )
    )

    respx.get("https://api.github.com/repos/octocat/single-repo/git/blobs/blob_js").mock(
        return_value=httpx.Response(
            200,
            json={"encoding": "base64", "content": base64.b64encode(b"console.log('hi');\n").decode()},
        )
    )

    ret = main(["octocat/single-repo", "--format", "json"])
    assert ret == 0
    captured = capsys.readouterr()
    data = json.loads(captured.out)
    assert data["username"] == "octocat/single-repo"
    assert data["repos_scanned"] == 1
    assert data["languages"][0]["language"] == "JavaScript"


@respx.mock
def test_cli_single_repo_flag_syntax(capsys):
    respx.get("https://api.github.com/repos/octocat/flagged-repo").mock(
        return_value=httpx.Response(
            200,
            json={
                "name": "flagged-repo",
                "owner": {"login": "octocat"},
                "default_branch": "main",
                "fork": False,
            },
        )
    )

    respx.get("https://api.github.com/repos/octocat/flagged-repo/git/trees/main", params={"recursive": "1"}).mock(
        return_value=httpx.Response(
            200,
            json={
                "truncated": False,
                "tree": [
                    {
                        "path": "main.py",
                        "type": "blob",
                        "sha": "blob_py",
                    }
                ],
            },
        )
    )

    respx.get("https://api.github.com/repos/octocat/flagged-repo/git/blobs/blob_py").mock(
        return_value=httpx.Response(
            200,
            json={"encoding": "base64", "content": base64.b64encode(b"print('single')\n").decode()},
        )
    )

    ret = main(["octocat", "--repo", "flagged-repo", "--format", "json"])
    assert ret == 0
    captured = capsys.readouterr()
    data = json.loads(captured.out)
    assert data["username"] == "octocat/flagged-repo"
    assert data["repos_scanned"] == 1
    assert data["languages"][0]["language"] == "Python"


@respx.mock
def test_cli_single_repo_not_found(capsys):
    respx.get("https://api.github.com/repos/octocat/missing-repo").mock(
        return_value=httpx.Response(404)
    )

    ret = main(["octocat/missing-repo", "--format", "json"])
    assert ret == 0
    captured = capsys.readouterr()
    data = json.loads(captured.out)
    assert data["username"] == "octocat/missing-repo"
    assert data["repos_scanned"] == 0
    assert data["languages"] == []


def test_cli_parser_include_private():
    parser = build_parser()
    args_default = parser.parse_args(["octocat"])
    assert args_default.include_private is False

    args_set = parser.parse_args(["octocat", "--include-private"])
    assert args_set.include_private is True


def test_cli_include_private_missing_token(capsys, monkeypatch):
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)
    ret = main(["octocat", "--include-private"])
    assert ret == 1
    captured = capsys.readouterr()
    assert "Error: --include-private requires a GitHub token. Set GITHUB_TOKEN or pass --token." in captured.err


@respx.mock
def test_cli_include_private_invalid_token(capsys, monkeypatch):
    respx.get("https://api.github.com/user").mock(
        return_value=httpx.Response(401, json={"message": "Bad credentials"})
    )
    ret = main(["octocat", "--include-private", "--token", "bad_token"])
    assert ret == 1
    captured = capsys.readouterr()
    assert "Error: Could not verify token. Ensure your GITHUB_TOKEN is valid." in captured.err


@respx.mock
def test_cli_include_private_mismatched_user(capsys):
    respx.get("https://api.github.com/user").mock(
        return_value=httpx.Response(200, json={"login": "otheruser"})
    )
    ret = main(["octocat", "--include-private", "--token", "my_token"])
    assert ret == 1
    captured = capsys.readouterr()
    assert "Error: --include-private can only scan your own account. Token belongs to 'otheruser' but target is 'octocat'." in captured.err


@respx.mock
def test_cli_include_private_success(capsys):
    respx.get("https://api.github.com/user").mock(
        return_value=httpx.Response(200, json={"login": "octocat"})
    )
    respx.get("https://api.github.com/user/repos", params={"per_page": "100", "type": "owner", "sort": "updated"}).mock(
        return_value=httpx.Response(
            200,
            json=[
                {
                    "name": "secret-project",
                    "owner": {"login": "octocat"},
                    "default_branch": "main",
                    "fork": False,
                    "private": True,
                }
            ],
        )
    )
    respx.get("https://api.github.com/repos/octocat/secret-project/git/trees/main", params={"recursive": "1"}).mock(
        return_value=httpx.Response(
            200,
            json={
                "truncated": False,
                "tree": [
                    {
                        "path": "secret.py",
                        "type": "blob",
                        "sha": "blob_secret_py",
                    }
                ],
            },
        )
    )
    respx.get("https://api.github.com/repos/octocat/secret-project/git/blobs/blob_secret_py").mock(
        return_value=httpx.Response(
            200,
            json={"encoding": "base64", "content": base64.b64encode(b"print('secret')\n").decode()},
        )
    )

    ret = main(["octocat", "--include-private", "--token", "valid_token", "--format", "json"])
    assert ret == 0
    captured = capsys.readouterr()
    data = json.loads(captured.out)
    assert data["username"] == "octocat"
    assert data["repos_scanned"] == 1
    assert data["languages"][0]["language"] == "Python"


@respx.mock
def test_cli_include_private_warns_zero_private(capsys, caplog):
    respx.get("https://api.github.com/user").mock(
        return_value=httpx.Response(200, json={"login": "octocat"})
    )
    respx.get("https://api.github.com/user/repos", params={"per_page": "100", "type": "owner", "sort": "updated"}).mock(
        return_value=httpx.Response(
            200,
            json=[
                {
                    "name": "public-only",
                    "owner": {"login": "octocat"},
                    "default_branch": "main",
                    "fork": False,
                    "private": False,
                }
            ],
        )
    )
    respx.get("https://api.github.com/repos/octocat/public-only/git/trees/main", params={"recursive": "1"}).mock(
        return_value=httpx.Response(
            200,
            json={
                "truncated": False,
                "tree": [
                    {
                        "path": "public.py",
                        "type": "blob",
                        "sha": "blob_pub_py",
                    }
                ],
            },
        )
    )
    respx.get("https://api.github.com/repos/octocat/public-only/git/blobs/blob_pub_py").mock(
        return_value=httpx.Response(
            200,
            json={"encoding": "base64", "content": base64.b64encode(b"print('public')\n").decode()},
        )
    )

    with caplog.at_level(logging.WARNING):
        ret = main(["octocat", "--include-private", "--token", "valid_token", "--format", "json"])
        assert ret == 0
        assert "No private repositories found for octocat" in caplog.text


@respx.mock
def test_cli_include_private_redundant_in_single_repo(capsys, caplog):
    respx.get("https://api.github.com/repos/octocat/single-repo").mock(
        return_value=httpx.Response(
            200,
            json={
                "name": "single-repo",
                "owner": {"login": "octocat"},
                "default_branch": "main",
                "fork": False,
                "private": True,
            },
        )
    )
    respx.get("https://api.github.com/repos/octocat/single-repo/git/trees/main", params={"recursive": "1"}).mock(
        return_value=httpx.Response(
            200,
            json={
                "truncated": False,
                "tree": [],
            },
        )
    )

    with caplog.at_level(logging.WARNING):
        ret = main(["octocat/single-repo", "--include-private", "--token", "valid_token", "--format", "json"])
        assert ret == 0
        assert "--include-private is not needed for single-repo mode" in caplog.text


