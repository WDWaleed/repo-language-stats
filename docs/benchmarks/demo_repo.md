# Benchmark Report: WDWaleed/repo-language-stats

**Timestamp:** `2026-11-21 06:28:22 UTC`  
**Target:** `WDWaleed/repo-language-stats` (Single Repository)  
**Branch:** `Default`  
**Host Environment:** Python 3.13.5 on Windows AMD64 (Intel64 Family 6 Model 140 Stepping 1, GenuineIntel)  

---

## 1. Executive Summary

| Metric | Measured Value |
|---|---|
| **Total Wall-Clock Time** | **`10.633s`** |
| **Network I/O Waiting Time** | `9.335s` (95.7%) |
| **Local CPU Computation Time** | `0.424s` (4.3%) |
| **Total HTTP Requests Made** | `17` requests |
| **Average Latency per Request** | `549.1 ms` |
| **HTTP Wire Data Transferred** | `212.1 KB` (`217,181` bytes) |
| **Raw Source Code Counted** | `138.4 KB` (`141,743` bytes) |
| **Protocol Bloat Ratio** | `1.53x` (Wire / Source code) |
| **Files Processed** | `16` files |
| **Source Lines Counted** | `4,289` lines |

---

## 2. Granular Timing Breakdown

| Operation | Category | Duration (s) | % of Tracked | Invocations | Avg per Call |
|---|---|---|---|---|---|
| List Repositories (`GET /repos`) | Network | 0.0000s | 0.0% | 0 | N/A |
| Branch Resolution (`GET /commits`) | Network | 0.0000s | 0.0% | 0 | N/A |
| Git Tree Fetch (`GET /git/trees`) | Network | 0.5534s | 5.7% | 1 | 553.42 ms |
| Git Blob Fetch (`GET /blobs`) | Network | 8.7817s | 90.0% | 16 | 548.86 ms |
| Base64 Decoding | CPU | 0.0008s | 0.0% | 16 | 0.05 ms |
| Tree Filtering (Vendor/Gen/Glob) | CPU | 0.4191s | 4.3% | 1 | 419.11 ms |
| Language Classification | CPU | 0.0023s | 0.0% | 16 | 0.14 ms |
| Notebook Parsing | CPU | 0.0000s | 0.0% | - | - |
| Line & Byte Counting | CPU | 0.0014s | 0.0% | 16 | 0.09 ms |
| Data Aggregation | CPU | 0.0002s | 0.0% | - | - |

---

## 3. Throughput & Network Efficiency

- **Effective Network Bandwidth:** `22.7 KB/s`
- **Overall Processing Speed:** `1.5 files/s` (`403 lines/s`)
- **Local CPU Compute Ceiling:** `37.8 files/s` (`10,121 lines/s`)

---

## 4. Bottleneck Diagnosis & Architectural Verdict

**Primary Bottleneck: Network I/O (95.7% of execution time)**

- **Analysis:** Execution is overwhelmingly bound by sequential HTTP roundtrip latency. With 17 individual API calls averaging 549.1ms each, the program spends most of its time waiting on remote network packets.
- **Rust Viability Assessment:** A rewrite in Rust **will NOT significantly speed up execution** if sequential GitHub API calls remain unchanged. Rust cannot overcome external network roundtrip latency. At best, Rust could only optimize the remaining 4.3% (0.424s) of local compute.
- **High-Leverage Optimization Levers:**
  1. **Concurrent Request Batching:** Fetching blobs concurrently using `asyncio` / `httpx.AsyncClient` or worker pools would drastically reduce overall latency (estimated 5x–15x speedup).
  2. **Repository Tarball Streaming:** Using GitHub's single archive endpoint (`GET /repos/{owner}/{repo}/tarball`) downloads all files in 1 roundtrip, bypassing individual blob roundtrips entirely (estimated 10x–30x speedup).

---

## 5. Pure Local Compute Ceiling (In-Memory Baseline)

To evaluate Python's local compute speed in isolation (without remote network latency), a synthetic in-memory workload was benchmarked on this host:
- **In-Memory Processing Speed:** `1,527 files/s` (`61,509 lines/s`)
- **Time to classify & count 1,000 files locally:** `0.655s`
