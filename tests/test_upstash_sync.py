"""Tests for scripts/push_to_upstash.py — payload serialization and Upstash REST integration."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import httpx
import pytest
import respx

# Make the scripts/ directory importable
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
from push_to_upstash import (  # noqa: E402
    UpstashClient,
    build_payload,
    sync_to_upstash,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

FAKE_URL = "https://test-redis.upstash.io"
FAKE_TOKEN = "test-token-abc123"


@pytest.fixture
def aggregate_stats_dict():
    """Simulate an AggregateStats-style dict (from rls --format json)."""
    return {
        "username": "WDWaleed",
        "repos_scanned": 10,
        "repos_skipped": 2,
        "total_bytes": 100000,
        "total_lines": 5000,
        "aggregate": {
            "Python": {"total_bytes": 60000, "total_lines": 3000, "file_count": 10},
            "TypeScript": {"total_bytes": 25000, "total_lines": 1200, "file_count": 5},
            "HTML": {"total_bytes": 10000, "total_lines": 600, "file_count": 2},
            "CSS": {"total_bytes": 5000, "total_lines": 200, "file_count": 1},
        },
    }


@pytest.fixture
def languages_list_stats_dict():
    """Simulate the CachedUserStats-style dict (already normalized, with pre-existing colors)."""
    return {
        "username": "mona",
        "repos_scanned": 3,
        "repos_skipped": 0,
        "total_bytes": 50000,
        "total_lines": 2500,
        "languages": [
            {"language": "Rust", "bytes": 35000, "lines": 1800, "files": 8, "color": "#dea584"},
            {"language": "Go", "bytes": 15000, "lines": 700, "files": 4},
        ],
    }


@pytest.fixture
def upstash_client():
    return UpstashClient(url=FAKE_URL, token=FAKE_TOKEN)


# ---------------------------------------------------------------------------
# build_payload tests
# ---------------------------------------------------------------------------


class TestBuildPayload:
    """Verify the CachedUserStats payload structure and color injection."""

    def test_basic_structure_from_aggregate(self, aggregate_stats_dict):
        payload = build_payload("WDWaleed", aggregate_stats_dict)

        assert payload["username"] == "WDWaleed"
        assert payload["repos_scanned"] == 10
        assert payload["repos_skipped"] == 2
        assert payload["total_bytes"] == 100000
        assert payload["total_lines"] == 5000
        assert isinstance(payload["languages"], list)
        assert len(payload["languages"]) == 4
        # ISO 8601 timestamp present
        assert "T" in payload["last_scanned"]
        assert "Z" in payload["last_scanned"] or "+" in payload["last_scanned"]

    def test_basic_structure_from_languages_list(self, languages_list_stats_dict):
        payload = build_payload("mona", languages_list_stats_dict)

        assert payload["username"] == "mona"
        assert len(payload["languages"]) == 2

    def test_languages_sorted_by_bytes_descending(self, aggregate_stats_dict):
        payload = build_payload("WDWaleed", aggregate_stats_dict)
        byte_counts = [l["bytes"] for l in payload["languages"]]
        assert byte_counts == sorted(byte_counts, reverse=True)

    def test_byte_and_line_percentages_sum_to_100(self, aggregate_stats_dict):
        payload = build_payload("WDWaleed", aggregate_stats_dict)
        total_bp = sum(l["byte_percent"] for l in payload["languages"])
        total_lp = sum(l["line_percent"] for l in payload["languages"])
        assert abs(total_bp - 100.0) < 0.5
        assert abs(total_lp - 100.0) < 0.5

    def test_color_injection_adds_hex_colors(self, aggregate_stats_dict):
        payload = build_payload("WDWaleed", aggregate_stats_dict, inject_colors=True)
        for lang in payload["languages"]:
            assert "color" in lang, f"Missing color for {lang['language']!r}"
            assert lang["color"].startswith("#"), f"Bad color for {lang['language']!r}: {lang['color']!r}"

    def test_color_injection_python_is_correct(self, aggregate_stats_dict):
        payload = build_payload("WDWaleed", aggregate_stats_dict, inject_colors=True)
        python_entry = next(l for l in payload["languages"] if l["language"] == "Python")
        assert python_entry["color"] == "#3572A5"

    def test_no_color_injection_omits_color(self, aggregate_stats_dict):
        payload = build_payload("WDWaleed", aggregate_stats_dict, inject_colors=False)
        for lang in payload["languages"]:
            assert "color" not in lang

    def test_preexisting_color_preserved(self, languages_list_stats_dict):
        """Pre-injected color in the input must be preserved, not overwritten."""
        payload = build_payload("mona", languages_list_stats_dict, inject_colors=True)
        rust_entry = next(l for l in payload["languages"] if l["language"] == "Rust")
        assert rust_entry["color"] == "#dea584"

    def test_per_language_fields_present(self, aggregate_stats_dict):
        payload = build_payload("WDWaleed", aggregate_stats_dict)
        required_fields = {"language", "bytes", "byte_percent", "lines", "line_percent", "files"}
        for lang in payload["languages"]:
            assert required_fields.issubset(lang.keys()), (
                f"Missing fields in {lang['language']!r}: {required_fields - lang.keys()}"
            )

    def test_payload_is_json_serializable(self, aggregate_stats_dict):
        payload = build_payload("WDWaleed", aggregate_stats_dict)
        serialized = json.dumps(payload)
        roundtripped = json.loads(serialized)
        assert roundtripped["username"] == "WDWaleed"


# ---------------------------------------------------------------------------
# UpstashClient tests (mocked with respx)
# ---------------------------------------------------------------------------


class TestUpstashClient:
    """Verify the REST client calls and retry logic using respx HTTP mocking."""

    @respx.mock
    def test_set_success(self, upstash_client):
        respx.post(FAKE_URL).mock(
            return_value=httpx.Response(200, json={"result": "OK"})
        )
        result = upstash_client.set("stats:WDWaleed", '{"username":"WDWaleed"}')
        assert result == {"result": "OK"}

    @respx.mock
    def test_set_with_expiry(self, upstash_client):
        route = respx.post(FAKE_URL).mock(
            return_value=httpx.Response(200, json={"result": "OK"})
        )
        upstash_client.set("some_key", "value", ex=600)
        # Verify the EX was included in the command body
        sent_body = json.loads(route.calls[0].request.content)
        assert "EX" in sent_body
        assert 600 in sent_body

    @respx.mock
    def test_set_retries_on_server_error(self, upstash_client):
        """Should retry and succeed on the 3rd attempt."""
        respx.post(FAKE_URL).mock(
            side_effect=[
                httpx.Response(500, text="Internal Server Error"),
                httpx.Response(500, text="Internal Server Error"),
                httpx.Response(200, json={"result": "OK"}),
            ]
        )
        # Patch sleep to avoid actually waiting
        import unittest.mock as mock
        with mock.patch("time.sleep"):
            result = upstash_client.set("key", "val", retries=3)
        assert result == {"result": "OK"}

    @respx.mock
    def test_set_raises_after_all_retries_exhausted(self, upstash_client):
        respx.post(FAKE_URL).mock(
            return_value=httpx.Response(503, text="Service Unavailable")
        )
        import unittest.mock as mock
        with mock.patch("time.sleep"):
            with pytest.raises(RuntimeError, match="All 3 attempts failed"):
                upstash_client.set("key", "val", retries=3)

    @respx.mock
    def test_set_raises_on_upstash_error_body(self, upstash_client):
        respx.post(FAKE_URL).mock(
            return_value=httpx.Response(200, json={"error": "WRONGTYPE"})
        )
        import unittest.mock as mock
        with mock.patch("time.sleep"):
            with pytest.raises(RuntimeError, match="Upstash error"):
                upstash_client.set("key", "val", retries=1)

    @respx.mock
    def test_get_success(self, upstash_client):
        respx.post(FAKE_URL).mock(
            return_value=httpx.Response(200, json={"result": '{"username":"WDWaleed"}'})
        )
        result = upstash_client.get("stats:WDWaleed")
        assert result["result"] == '{"username":"WDWaleed"}'


# ---------------------------------------------------------------------------
# sync_to_upstash integration tests (dry-run + mocked)
# ---------------------------------------------------------------------------


class TestSyncToUpstash:
    """Verify the high-level sync function: payload building + client call."""

    def test_dry_run_does_not_call_upstash(self, aggregate_stats_dict, upstash_client):
        with respx.mock() as mock_router:
            payload = sync_to_upstash(
                username="WDWaleed",
                stats=aggregate_stats_dict,
                client=upstash_client,
                dry_run=True,
            )
        # No HTTP calls should have been made in dry-run mode
        assert len(mock_router.calls) == 0
        assert payload["username"] == "WDWaleed"

    @respx.mock
    def test_live_sync_uses_correct_redis_key(self, aggregate_stats_dict, upstash_client):
        route = respx.post(FAKE_URL).mock(
            return_value=httpx.Response(200, json={"result": "OK"})
        )
        sync_to_upstash(
            username="WDWaleed",
            stats=aggregate_stats_dict,
            client=upstash_client,
        )
        sent_body = json.loads(route.calls[0].request.content)
        # Command: ["SET", "stats:WDWaleed", <json_payload>]
        assert sent_body[0] == "SET"
        assert sent_body[1] == "stats:WDWaleed"
        # The JSON value must be parseable and contain expected fields
        stored = json.loads(sent_body[2])
        assert stored["username"] == "WDWaleed"
        assert isinstance(stored["languages"], list)
        assert len(stored["languages"]) == 4

    @respx.mock
    def test_live_sync_payload_has_colors(self, aggregate_stats_dict, upstash_client):
        route = respx.post(FAKE_URL).mock(
            return_value=httpx.Response(200, json={"result": "OK"})
        )
        sync_to_upstash("WDWaleed", aggregate_stats_dict, upstash_client, inject_colors=True)
        sent = json.loads(json.loads(route.calls[0].request.content)[2])
        for lang in sent["languages"]:
            assert lang.get("color", "").startswith("#"), (
                f"Missing/invalid color for {lang['language']!r}"
            )

    @respx.mock
    def test_sync_decision_d5_key_format(self, aggregate_stats_dict, upstash_client):
        """Decision D5: key must be `stats:{username}`."""
        route = respx.post(FAKE_URL).mock(
            return_value=httpx.Response(200, json={"result": "OK"})
        )
        sync_to_upstash("octocat", aggregate_stats_dict, upstash_client)
        sent_body = json.loads(route.calls[0].request.content)
        assert sent_body[1] == "stats:octocat"
