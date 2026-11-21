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
