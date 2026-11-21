"""Profiling and benchmarking collector for measuring network vs CPU performance."""

from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
import platform
import time
from typing import Generator

from rich.console import Console
from rich.table import Table


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


def resolve_benchmark_path(
    target_str: str,
    custom_output: Path | str | None = None,
    base_dir: Path | None = None,
) -> tuple[Path, bool]:
    """Determine the benchmark report path and whether to append.

    Rules:
    - If custom_output is set: return (custom_output, False)
    - If target is 'WDWaleed/repo-language-stats' (case-insensitive): (base_dir / 'docs/benchmarks/demo_repo.md', False)
    - If target is 'WDWaleed' (case-insensitive): (base_dir / 'docs/benchmarks/demo_profile.md', False)
    - Otherwise: (base_dir / 'docs/benchmarks/others.md', True)
    """
    if custom_output:
        return (Path(custom_output), False)

    root = base_dir or Path.cwd()
    benchmarks_dir = root / "docs" / "benchmarks"

    cleaned = target_str.strip().lower()
    if cleaned in ("wdwaleed/repo-language-stats", "wdwaleed/repo-language-stats.git"):
        return (benchmarks_dir / "demo_repo.md", False)
    elif cleaned == "wdwaleed":
        return (benchmarks_dir / "demo_profile.md", False)
    else:
        return (benchmarks_dir / "others.md", True)


def generate_markdown_report(
    benchmark: BenchmarkCollector,
    target: str,
    branch: str | None = None,
    is_single_repo: bool = False,
    now: datetime | None = None,
) -> str:
    """Generate a comprehensive markdown benchmark report."""
    dt = now or datetime.now(timezone.utc)
    dt_str = dt.strftime("%Y-%m-%d %H:%M:%S UTC")

    tracked_time = benchmark.total_network_time_s + benchmark.total_cpu_time_s

    def _calc_pct(duration_ns: int) -> float:
        if tracked_time <= 0.0:
            return 0.0
        return ((duration_ns / 1_000_000_000.0) / tracked_time) * 100.0

    def _calc_avg_ms(duration_ns: int, count: int) -> str:
        if count <= 0:
            return "N/A"
        avg_ms = (duration_ns / count) / 1_000_000.0
        return f"{avg_ms:.2f} ms"

    # Verdict generation
    net_pct = benchmark.network_percentage
    cpu_pct = benchmark.cpu_percentage

    if net_pct >= 70.0:
        verdict = (
            f"**Primary Bottleneck: Network I/O ({net_pct:.1f}% of execution time)**\n\n"
            f"- **Analysis:** Execution is overwhelmingly bound by sequential HTTP roundtrip latency. "
            f"With {benchmark.total_requests} individual API calls averaging {benchmark.avg_request_latency_ms:.1f}ms each, "
            f"the program spends most of its time waiting on remote network packets.\n"
            f"- **Rust Viability Assessment:** A rewrite in Rust **will NOT significantly speed up execution** if sequential "
            f"GitHub API calls remain unchanged. Rust cannot overcome external network roundtrip latency. At best, Rust could only "
            f"optimize the remaining {cpu_pct:.1f}% ({benchmark.total_cpu_time_s:.3f}s) of local compute.\n"
            f"- **High-Leverage Optimization Levers:**\n"
            f"  1. **Concurrent Request Batching:** Fetching blobs concurrently using `asyncio` / `httpx.AsyncClient` or worker pools would drastically reduce overall latency (estimated 5x–15x speedup).\n"
            f"  2. **Repository Tarball Streaming:** Using GitHub's single archive endpoint (`GET /repos/{{owner}}/{{repo}}/tarball`) downloads all files in 1 roundtrip, bypassing individual blob roundtrips entirely (estimated 10x–30x speedup)."
        )
    elif cpu_pct >= 50.0:
        verdict = (
            f"**Primary Bottleneck: Local CPU Computation ({cpu_pct:.1f}% of execution time)**\n\n"
            f"- **Analysis:** Execution is CPU-bound. Local processing (Linguist regex classification, tree filtering, notebook JSON parsing, and line counting) accounts for the majority of execution time.\n"
            f"- **Rust Viability Assessment:** A rewrite in Rust **is worthwhile to consider**. Rust's zero-cost abstractions, optimized regex engines, and compiled binary performance could accelerate the CPU portion by 10x–50x."
        )
    else:
        verdict = (
            f"**Balanced Workload:** Network I/O accounts for {net_pct:.1f}% and local CPU accounts for {cpu_pct:.1f}%.\n\n"
            f"- **Optimization Assessment:** Both network concurrency and compute optimization would yield measurable benefits."
        )

    branch_display = branch if branch else "Default"
    scope_display = "Single Repository" if is_single_repo else "User Portfolio"

    rows = [
        ("List Repositories (`GET /repos`)", "Network", benchmark.t_list_repos_ns / 1e9, _calc_pct(benchmark.t_list_repos_ns), benchmark.req_count_repos, _calc_avg_ms(benchmark.t_list_repos_ns, benchmark.req_count_repos)),
        ("Branch Resolution (`GET /commits`)", "Network", benchmark.t_ref_resolution_ns / 1e9, _calc_pct(benchmark.t_ref_resolution_ns), benchmark.req_count_refs, _calc_avg_ms(benchmark.t_ref_resolution_ns, benchmark.req_count_refs)),
        ("Git Tree Fetch (`GET /git/trees`)", "Network", benchmark.t_get_tree_ns / 1e9, _calc_pct(benchmark.t_get_tree_ns), benchmark.req_count_trees, _calc_avg_ms(benchmark.t_get_tree_ns, benchmark.req_count_trees)),
        ("Git Blob Fetch (`GET /blobs`)", "Network", benchmark.t_get_blob_ns / 1e9, _calc_pct(benchmark.t_get_blob_ns), benchmark.req_count_blobs, _calc_avg_ms(benchmark.t_get_blob_ns, benchmark.req_count_blobs)),
        ("Base64 Decoding", "CPU", benchmark.t_decode_base64_ns / 1e9, _calc_pct(benchmark.t_decode_base64_ns), benchmark.req_count_blobs, _calc_avg_ms(benchmark.t_decode_base64_ns, benchmark.req_count_blobs)),
        ("Tree Filtering (Vendor/Gen/Glob)", "CPU", benchmark.t_filter_tree_ns / 1e9, _calc_pct(benchmark.t_filter_tree_ns), benchmark.repos_benchmarked, _calc_avg_ms(benchmark.t_filter_tree_ns, benchmark.repos_benchmarked)),
        ("Language Classification", "CPU", benchmark.t_classify_ns / 1e9, _calc_pct(benchmark.t_classify_ns), benchmark.files_processed, _calc_avg_ms(benchmark.t_classify_ns, benchmark.files_processed)),
        ("Notebook Parsing", "CPU", benchmark.t_parse_notebook_ns / 1e9, _calc_pct(benchmark.t_parse_notebook_ns), "-", "-"),
        ("Line & Byte Counting", "CPU", benchmark.t_count_metrics_ns / 1e9, _calc_pct(benchmark.t_count_metrics_ns), benchmark.files_processed, _calc_avg_ms(benchmark.t_count_metrics_ns, benchmark.files_processed)),
        ("Data Aggregation", "CPU", benchmark.t_aggregation_ns / 1e9, _calc_pct(benchmark.t_aggregation_ns), "-", "-"),
    ]

    table_lines = [
        "| Operation | Category | Duration (s) | % of Tracked | Invocations | Avg per Call |",
        "|---|---|---|---|---|---|",
    ]
    for name, cat, dur, pct, inv, avg in rows:
        table_lines.append(f"| {name} | {cat} | {dur:.4f}s | {pct:.1f}% | {inv} | {avg} |")

    table_str = "\n".join(table_lines)

    report = f"""# Benchmark Report: {target}

**Timestamp:** `{dt_str}`  
**Target:** `{target}` ({scope_display})  
**Branch:** `{branch_display}`  
**Host Environment:** Python {platform.python_version()} on {platform.system()} {platform.machine()} ({platform.processor() or 'CPU'})  

---

## 1. Executive Summary

| Metric | Measured Value |
|---|---|
| **Total Wall-Clock Time** | **`{benchmark.total_wall_clock_s:.3f}s`** |
| **Network I/O Waiting Time** | `{benchmark.total_network_time_s:.3f}s` ({benchmark.network_percentage:.1f}%) |
| **Local CPU Computation Time** | `{benchmark.total_cpu_time_s:.3f}s` ({benchmark.cpu_percentage:.1f}%) |
| **Total HTTP Requests Made** | `{benchmark.total_requests}` requests |
| **Average Latency per Request** | `{benchmark.avg_request_latency_ms:.1f} ms` |
| **HTTP Wire Data Transferred** | `{benchmark.wire_bytes_downloaded / 1024.0:.1f} KB` (`{benchmark.wire_bytes_downloaded:,}` bytes) |
| **Raw Source Code Counted** | `{benchmark.source_bytes_counted / 1024.0:.1f} KB` (`{benchmark.source_bytes_counted:,}` bytes) |
| **Protocol Bloat Ratio** | `{benchmark.protocol_bloat_ratio:.2f}x` (Wire / Source code) |
| **Files Processed** | `{benchmark.files_processed}` files |
| **Source Lines Counted** | `{benchmark.lines_counted:,}` lines |

---

## 2. Granular Timing Breakdown

{table_str}

---

## 3. Throughput & Network Efficiency

- **Effective Network Bandwidth:** `{benchmark.effective_bandwidth_kb_s:.1f} KB/s`
- **Overall Processing Speed:** `{benchmark.files_per_second:.1f} files/s` (`{benchmark.lines_per_second:,.0f} lines/s`)
- **Local CPU Compute Ceiling:** `{benchmark.cpu_files_per_second:.1f} files/s` (`{benchmark.cpu_lines_per_second:,.0f} lines/s`)

---

## 4. Bottleneck Diagnosis & Architectural Verdict

{verdict}
"""
    return report.strip()


def save_benchmark_report(
    report_text: str,
    path: Path | str,
    append: bool = False,
) -> None:
    """Save benchmark markdown report to disk, appending or overwriting as specified."""
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)

    if append and p.is_file():
        existing = p.read_text(encoding="utf-8").rstrip()
        content = f"{existing}\n\n---\n\n{report_text}\n"
    else:
        content = f"{report_text}\n"

    p.write_text(content, encoding="utf-8")


def print_terminal_benchmark(
    benchmark: BenchmarkCollector,
    target: str,
    console: Console | None = None,
) -> None:
    """Display an immediate, styled benchmark summary table directly in the terminal."""
    con = console or Console()

    table = Table(
        title=f"Benchmark Profile: {target}",
        title_style="bold cyan",
        header_style="bold magenta",
        show_footer=False,
    )

    table.add_column("Category", justify="left")
    table.add_column("Duration", justify="right")
    table.add_column("% Share", justify="right")
    table.add_column("Requests / Files", justify="right")
    table.add_column("Throughput / Latency", justify="right")

    table.add_row(
        "Network I/O (HTTP)",
        f"{benchmark.total_network_time_s:.3f}s",
        f"{benchmark.network_percentage:.1f}%",
        f"{benchmark.total_requests} reqs",
        f"{benchmark.avg_request_latency_ms:.1f} ms/req",
    )
    table.add_row(
        "Local CPU Computation",
        f"{benchmark.total_cpu_time_s:.3f}s",
        f"{benchmark.cpu_percentage:.1f}%",
        f"{benchmark.files_processed} files",
        f"{benchmark.cpu_files_per_second:.0f} files/s",
    )
    table.add_row(
        "[bold]Total Wall Clock[/bold]",
        f"[bold]{benchmark.total_wall_clock_s:.3f}s[/bold]",
        "[bold]100.0%[/bold]",
        f"[bold]{benchmark.wire_bytes_downloaded / 1024:.1f} KB wire[/bold]",
        f"[bold]{benchmark.files_per_second:.1f} files/s[/bold]",
    )

    con.print("\n")
    con.print(table)

