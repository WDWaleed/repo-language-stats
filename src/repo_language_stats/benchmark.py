"""Profiling and benchmarking collector for measuring network vs CPU performance."""

from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass
import time
from typing import Generator


@dataclass
class BenchmarkCollector:
    """Collects fine-grained execution metrics separating network I/O from CPU computation."""

    # Network timers (nanoseconds)
    t_list_repos_ns: int = 0
    t_ref_resolution_ns: int = 0
    t_get_tree_ns: int = 0
    t_get_blob_ns: int = 0

    # CPU timers (nanoseconds)
    t_filter_tree_ns: int = 0
    t_classify_ns: int = 0
    t_decode_base64_ns: int = 0
    t_parse_notebook_ns: int = 0
    t_count_metrics_ns: int = 0
    t_aggregation_ns: int = 0

    # Total wall-clock timer (nanoseconds)
    t_wall_clock_ns: int = 0

    # Network request counters
    req_count_repos: int = 0
    req_count_refs: int = 0
    req_count_trees: int = 0
    req_count_blobs: int = 0

    # Volume and throughput counters
    wire_bytes_downloaded: int = 0
    source_bytes_counted: int = 0
    files_processed: int = 0
    lines_counted: int = 0
    repos_benchmarked: int = 0

    @contextmanager
    def measure(self, category: str) -> Generator[None, None, None]:
        """Context manager to measure elapsed time for a given category.

        Supported categories:
        - Network: 'list_repos', 'ref_resolution', 'get_tree', 'get_blob'
        - CPU: 'filter_tree', 'classify', 'decode_base64', 'parse_notebook', 'count_metrics', 'aggregation'
        - Overall: 'wall_clock'
        """
        start = time.perf_counter_ns()
        try:
            yield
        finally:
            elapsed = time.perf_counter_ns() - start

            if category == "list_repos":
                self.t_list_repos_ns += elapsed
                self.req_count_repos += 1
            elif category == "ref_resolution":
                self.t_ref_resolution_ns += elapsed
                self.req_count_refs += 1
            elif category == "get_tree":
                self.t_get_tree_ns += elapsed
                self.req_count_trees += 1
            elif category == "get_blob":
                self.t_get_blob_ns += elapsed
                self.req_count_blobs += 1
            elif category == "filter_tree":
                self.t_filter_tree_ns += elapsed
            elif category == "classify":
                self.t_classify_ns += elapsed
            elif category == "decode_base64":
                self.t_decode_base64_ns += elapsed
            elif category == "parse_notebook":
                self.t_parse_notebook_ns += elapsed
            elif category == "count_metrics":
                self.t_count_metrics_ns += elapsed
            elif category == "aggregation":
                self.t_aggregation_ns += elapsed
            elif category == "wall_clock":
                self.t_wall_clock_ns += elapsed

    def record_response_bytes(self, size: int) -> None:
        """Record raw response bytes transferred over the HTTP wire."""
        if size > 0:
            self.wire_bytes_downloaded += size

    def record_source_bytes(self, size: int) -> None:
        """Record raw unencoded source code bytes counted."""
        if size > 0:
            self.source_bytes_counted += size

    def record_file_processed(self, lines: int = 0) -> None:
        """Increment count of processed files and add line count."""
        self.files_processed += 1
        if lines > 0:
            self.lines_counted += lines

    # Computed timing properties (in seconds)
    @property
    def total_network_time_s(self) -> float:
        """Total time spent waiting on network operations (seconds)."""
        total_ns = (
            self.t_list_repos_ns
            + self.t_ref_resolution_ns
            + self.t_get_tree_ns
            + self.t_get_blob_ns
        )
        return total_ns / 1_000_000_000.0

    @property
    def total_cpu_time_s(self) -> float:
        """Total time spent on local CPU computation (seconds)."""
        total_ns = (
            self.t_filter_tree_ns
            + self.t_classify_ns
            + self.t_decode_base64_ns
            + self.t_parse_notebook_ns
            + self.t_count_metrics_ns
            + self.t_aggregation_ns
        )
        return total_ns / 1_000_000_000.0

    @property
    def total_wall_clock_s(self) -> float:
        """Total measured wall-clock time (seconds).

        Falls back to sum of network + CPU if wall clock wasn't explicitly timed.
        """
        if self.t_wall_clock_ns > 0:
            return self.t_wall_clock_ns / 1_000_000_000.0
        return self.total_network_time_s + self.total_cpu_time_s

    @property
    def total_requests(self) -> int:
        """Total number of GitHub HTTP API requests made."""
        return (
            self.req_count_repos
            + self.req_count_refs
            + self.req_count_trees
            + self.req_count_blobs
        )

    @property
    def network_percentage(self) -> float:
        """Percentage of tracked time spent on network I/O."""
        tracked = self.total_network_time_s + self.total_cpu_time_s
        if tracked <= 0.0:
            return 0.0
        return (self.total_network_time_s / tracked) * 100.0

    @property
    def cpu_percentage(self) -> float:
        """Percentage of tracked time spent on local CPU computation."""
        tracked = self.total_network_time_s + self.total_cpu_time_s
        if tracked <= 0.0:
            return 0.0
        return (self.total_cpu_time_s / tracked) * 100.0

    @property
    def effective_bandwidth_kb_s(self) -> float:
        """Effective transfer throughput over HTTP in kilobytes per second."""
        if self.total_network_time_s <= 0.0 or self.wire_bytes_downloaded <= 0:
            return 0.0
        return (self.wire_bytes_downloaded / 1024.0) / self.total_network_time_s

    @property
    def protocol_bloat_ratio(self) -> float:
        """Ratio of HTTP wire bytes downloaded to actual source bytes counted.

        A ratio > 1.33 typically indicates Base64 expansion and JSON overhead.
        """
        if self.source_bytes_counted <= 0:
            return 1.0 if self.wire_bytes_downloaded == 0 else float(self.wire_bytes_downloaded)
        return self.wire_bytes_downloaded / self.source_bytes_counted

    @property
    def avg_request_latency_ms(self) -> float:
        """Average round-trip latency per HTTP request in milliseconds."""
        if self.total_requests <= 0:
            return 0.0
        return (self.total_network_time_s / self.total_requests) * 1000.0

    @property
    def files_per_second(self) -> float:
        """Overall throughput in files processed per wall-clock second."""
        if self.total_wall_clock_s <= 0.0 or self.files_processed <= 0:
            return 0.0
        return self.files_processed / self.total_wall_clock_s

    @property
    def lines_per_second(self) -> float:
        """Overall throughput in lines counted per wall-clock second."""
        if self.total_wall_clock_s <= 0.0 or self.lines_counted <= 0:
            return 0.0
        return self.lines_counted / self.total_wall_clock_s

    @property
    def cpu_files_per_second(self) -> float:
        """Pure CPU throughput in files processed per second of computation time."""
        if self.total_cpu_time_s <= 0.0 or self.files_processed <= 0:
            return 0.0
        return self.files_processed / self.total_cpu_time_s

    @property
    def cpu_lines_per_second(self) -> float:
        """Pure CPU throughput in lines counted per second of computation time."""
        if self.total_cpu_time_s <= 0.0 or self.lines_counted <= 0:
            return 0.0
        return self.lines_counted / self.total_cpu_time_s
