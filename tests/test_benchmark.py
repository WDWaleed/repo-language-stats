"""Unit tests for the BenchmarkCollector metrics engine."""

import time
import pytest

from repo_language_stats.benchmark import BenchmarkCollector


def test_benchmark_collector_initial_state():
    b = BenchmarkCollector()
    assert b.total_network_time_s == 0.0
    assert b.total_cpu_time_s == 0.0
    assert b.total_wall_clock_s == 0.0
    assert b.total_requests == 0
    assert b.network_percentage == 0.0
    assert b.cpu_percentage == 0.0
    assert b.effective_bandwidth_kb_s == 0.0
    assert b.protocol_bloat_ratio == 1.0
    assert b.avg_request_latency_ms == 0.0
    assert b.files_per_second == 0.0
    assert b.lines_per_second == 0.0
    assert b.cpu_files_per_second == 0.0
    assert b.cpu_lines_per_second == 0.0


def test_benchmark_measure_context_manager():
    b = BenchmarkCollector()

    with b.measure("list_repos"):
        time.sleep(0.01)

    with b.measure("classify"):
        time.sleep(0.01)

    assert b.req_count_repos == 1
    assert b.t_list_repos_ns > 0
    assert b.t_classify_ns > 0
    assert b.total_network_time_s > 0.0
    assert b.total_cpu_time_s > 0.0
    assert b.total_requests == 1
    assert b.network_percentage > 0.0
    assert b.cpu_percentage > 0.0
    assert pytest.approx(b.network_percentage + b.cpu_percentage, 0.1) == 100.0


def test_benchmark_measure_all_categories():
    b = BenchmarkCollector()

    # Network categories
    categories_network = ["list_repos", "ref_resolution", "get_tree", "get_blob"]
    for cat in categories_network:
        with b.measure(cat):
            pass

    assert b.req_count_repos == 1
    assert b.req_count_refs == 1
    assert b.req_count_trees == 1
    assert b.req_count_blobs == 1
    assert b.total_requests == 4

    # CPU categories
    categories_cpu = [
        "filter_tree",
        "classify",
        "decode_base64",
        "parse_notebook",
        "count_metrics",
        "aggregation",
    ]
    for cat in categories_cpu:
        with b.measure(cat):
            pass

    # Wall clock
    with b.measure("wall_clock"):
        pass

    assert b.t_wall_clock_ns > 0


def test_benchmark_counters_and_throughput():
    b = BenchmarkCollector()
    b.t_wall_clock_ns = 2_000_000_000  # 2.0 seconds
    b.t_get_blob_ns = 1_500_000_000    # 1.5 seconds network
    b.req_count_blobs = 10
    b.t_count_metrics_ns = 500_000_000  # 0.5 seconds CPU

    b.record_response_bytes(204_800)  # 200 KB over wire
    b.record_source_bytes(150_000)    # 150 KB source code
    b.record_file_processed(lines=500)
    b.record_file_processed(lines=500)

    assert b.files_processed == 2
    assert b.lines_counted == 1000
    assert b.wire_bytes_downloaded == 204_800
    assert b.source_bytes_counted == 150_000

    # Timing assertions
    assert b.total_network_time_s == 1.5
    assert b.total_cpu_time_s == 0.5
    assert b.total_wall_clock_s == 2.0
    assert b.network_percentage == 75.0
    assert b.cpu_percentage == 25.0

    # Latency: 1.5s / 10 requests = 150ms
    assert b.avg_request_latency_ms == 150.0

    # Effective bandwidth: 200 KB / 1.5s = ~133.33 KB/s
    assert pytest.approx(b.effective_bandwidth_kb_s, 0.1) == (200.0 / 1.5)

    # Bloat ratio: 204800 / 150000 = ~1.365
    assert pytest.approx(b.protocol_bloat_ratio, 0.001) == 204800 / 150000

    # Throughput
    assert b.files_per_second == 1.0  # 2 files / 2.0s
    assert b.lines_per_second == 500.0  # 1000 lines / 2.0s
    assert b.cpu_files_per_second == 4.0  # 2 files / 0.5s CPU
    assert b.cpu_lines_per_second == 2000.0  # 1000 lines / 0.5s CPU


import base64
import httpx
import respx
from repo_language_stats.github_api import GitHubAPIClient
from repo_language_stats.cli import scan_single_repo


@respx.mock
def test_github_api_client_with_benchmark():
    bm = BenchmarkCollector()

    respx.get("https://api.github.com/repos/octocat/repo1/commits/dev").mock(
        return_value=httpx.Response(
            200,
            json={"sha": "c1", "commit": {"tree": {"sha": "t1"}}},
        )
    )
    respx.get("https://api.github.com/repos/octocat/repo1/git/trees/t1").mock(
        return_value=httpx.Response(
            200,
            json={"sha": "t1", "truncated": False, "tree": []},
        )
    )
    respx.get("https://api.github.com/repos/octocat/repo1/git/blobs/b1").mock(
        return_value=httpx.Response(
            200,
            json={"encoding": "base64", "content": base64.b64encode(b"hello world\n").decode("ascii")},
        )
    )

    with GitHubAPIClient(benchmark=bm) as client:
        sha = client.get_ref_tree_sha("octocat", "repo1", "dev")
        assert sha == "t1"

        entries, _ = client.get_tree("octocat", "repo1", "t1")
        assert entries == []

        blob = client.get_blob("octocat", "repo1", "b1")
        assert blob == b"hello world\n"

    assert bm.req_count_refs == 1
    assert bm.req_count_trees == 1
    assert bm.req_count_blobs == 1
    assert bm.total_requests == 3
    assert bm.wire_bytes_downloaded > 0
    assert bm.t_ref_resolution_ns > 0
    assert bm.t_get_tree_ns > 0
    assert bm.t_get_blob_ns > 0
    assert bm.t_decode_base64_ns > 0


@respx.mock
def test_scan_single_repo_with_benchmark():
    bm = BenchmarkCollector()

    respx.get("https://api.github.com/repos/octocat/repo1").mock(
        return_value=httpx.Response(
            200,
            json={
                "name": "repo1",
                "owner": {"login": "octocat"},
                "default_branch": "main",
                "fork": False,
                "private": False,
                "size": 100,
            },
        )
    )
    respx.get("https://api.github.com/repos/octocat/repo1/git/trees/main").mock(
        return_value=httpx.Response(
            200,
            json={
                "sha": "main",
                "truncated": False,
                "tree": [
                    {"path": "main.py", "mode": "100644", "type": "blob", "sha": "blob1", "size": 35},
                ],
            },
        )
    )
    respx.get("https://api.github.com/repos/octocat/repo1/git/blobs/blob1").mock(
        return_value=httpx.Response(
            200,
            json={
                "encoding": "base64",
                "content": base64.b64encode(b"def foo():\n    return 42\n").decode("ascii"),
            },
        )
    )

    with GitHubAPIClient(benchmark=bm) as client:
        stats = scan_single_repo(
            owner="octocat",
            repo_name="repo1",
            client=client,
            benchmark=bm,
        )

    assert stats is not None
    assert bm.repos_benchmarked == 1
    assert bm.files_processed == 1
    assert bm.lines_counted == 2
    assert bm.source_bytes_counted == len(b"def foo():\n    return 42\n")
    assert bm.t_filter_tree_ns > 0
    assert bm.t_classify_ns > 0
    assert bm.t_count_metrics_ns > 0
    assert bm.t_aggregation_ns > 0
    assert bm.total_network_time_s > 0.0
    assert bm.total_cpu_time_s > 0.0


from pathlib import Path
from repo_language_stats.benchmark import (
    generate_markdown_report,
    print_terminal_benchmark,
    resolve_benchmark_path,
    run_synthetic_benchmark,
    save_benchmark_report,
)
from rich.console import Console


def test_resolve_benchmark_path():
    root = Path("/dummy/project")

    # Demo repo
    p, append = resolve_benchmark_path("WDWaleed/repo-language-stats", base_dir=root)
    assert p == root / "docs" / "benchmarks" / "demo_repo.md"
    assert append is False

    # Demo profile
    p, append = resolve_benchmark_path("WDWaleed", base_dir=root)
    assert p == root / "docs" / "benchmarks" / "demo_profile.md"
    assert append is False

    # Others
    p, append = resolve_benchmark_path("octocat/Hello-World", base_dir=root)
    assert p == root / "docs" / "benchmarks" / "others.md"
    assert append is True

    # Custom override
    custom = Path("/tmp/my_benchmark.md")
    p, append = resolve_benchmark_path("WDWaleed", custom_output=custom, base_dir=root)
    assert p == custom
    assert append is False


def test_generate_markdown_report():
    b = BenchmarkCollector()
    b.t_wall_clock_ns = 2_000_000_000
    b.t_get_blob_ns = 1_800_000_000
    b.req_count_blobs = 10
    b.t_classify_ns = 200_000_000
    b.record_response_bytes(100_000)
    b.record_source_bytes(75_000)
    b.record_file_processed(lines=300)

    report = generate_markdown_report(
        benchmark=b,
        target="WDWaleed/repo-language-stats",
        branch="main",
        is_single_repo=True,
    )

    assert "# Benchmark Report: WDWaleed/repo-language-stats" in report
    assert "Single Repository" in report
    assert "Branch:** `main`" in report
    assert "Total Wall-Clock Time" in report
    assert "Primary Bottleneck: Network I/O" in report
    assert "Rust Viability Assessment" in report


def test_save_benchmark_report(tmp_path: Path):
    target_file = tmp_path / "docs" / "benchmarks" / "test.md"

    # Write new
    save_benchmark_report("# Run 1", target_file, append=False)
    assert target_file.read_text(encoding="utf-8").strip() == "# Run 1"

    # Append
    save_benchmark_report("# Run 2", target_file, append=True)
    content = target_file.read_text(encoding="utf-8")
    assert "# Run 1" in content
    assert "---" in content
    assert "# Run 2" in content


def test_print_terminal_benchmark():
    b = BenchmarkCollector()
    b.t_get_blob_ns = 1_000_000_000
    b.req_count_blobs = 5
    b.t_classify_ns = 200_000_000
    b.record_response_bytes(50_000)
    b.record_file_processed(lines=100)

    console = Console(record=True, width=120)
    print_terminal_benchmark(b, target="octocat/repo1", console=console)
    output = console.export_text()

    assert "Benchmark Profile: octocat/repo1" in output
    assert "Network I/O" in output
    assert "Local CPU Computation" in output


def test_run_synthetic_benchmark():
    bm = run_synthetic_benchmark(file_count=100)
    assert bm.repos_benchmarked == 1
    assert bm.files_processed > 0
    assert bm.lines_counted > 0
    assert bm.source_bytes_counted > 0
    assert bm.total_cpu_time_s > 0.0
    assert bm.cpu_files_per_second > 0.0
    assert bm.cpu_lines_per_second > 0.0
    assert bm.t_filter_tree_ns > 0
    assert bm.t_classify_ns > 0
    assert bm.t_count_metrics_ns > 0
    assert bm.t_aggregation_ns > 0



