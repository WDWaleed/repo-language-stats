# Benchmark Report: WDWaleed

**Timestamp:** `2026-11-21 06:32:14 UTC`  
**Target:** `WDWaleed` (User Portfolio)  
**Branch:** `Default`  
**Host Environment:** Python 3.13.5 on Windows AMD64 (Intel64 Family 6 Model 140 Stepping 1, GenuineIntel)  

---

## 1. Executive Summary

| Metric | Measured Value |
|---|---|
| **Total Wall-Clock Time** | **`179.694s`** |
| **Network I/O Waiting Time** | `178.928s` (99.6%) |
| **Local CPU Computation Time** | `0.707s` (0.4%) |
| **Total HTTP Requests Made** | `325` requests |
| **Average Latency per Request** | `550.5 ms` |
| **HTTP Wire Data Transferred** | `2622.3 KB` (`2,685,268` bytes) |
| **Raw Source Code Counted** | `941.7 KB` (`964,326` bytes) |
| **Protocol Bloat Ratio** | `2.78x` (Wire / Source code) |
| **Files Processed** | `295` files |
| **Source Lines Counted** | `29,476` lines |

---

## 2. Granular Timing Breakdown

| Operation | Category | Duration (s) | % of Tracked | Invocations | Avg per Call |
|---|---|---|---|---|---|
| List Repositories (`GET /repos`) | Network | 1.2257s | 0.7% | 1 | 1225.70 ms |
| Branch Resolution (`GET /commits`) | Network | 0.0000s | 0.0% | 0 | N/A |
| Git Tree Fetch (`GET /git/trees`) | Network | 17.0835s | 9.5% | 29 | 589.09 ms |
| Git Blob Fetch (`GET /blobs`) | Network | 160.6184s | 89.4% | 295 | 544.47 ms |
| Base64 Decoding | CPU | 0.0099s | 0.0% | 295 | 0.03 ms |
| Tree Filtering (Vendor/Gen/Glob) | CPU | 0.5917s | 0.3% | 29 | 20.40 ms |
| Language Classification | CPU | 0.0518s | 0.0% | 295 | 0.18 ms |
| Notebook Parsing | CPU | 0.0433s | 0.0% | - | - |
| Line & Byte Counting | CPU | 0.0061s | 0.0% | 295 | 0.02 ms |
| Data Aggregation | CPU | 0.0038s | 0.0% | - | - |

---

## 3. Throughput & Network Efficiency

- **Effective Network Bandwidth:** `14.7 KB/s`
- **Overall Processing Speed:** `1.6 files/s` (`164 lines/s`)
- **Local CPU Compute Ceiling:** `417.5 files/s` (`41,713 lines/s`)

---

## 4. Bottleneck Diagnosis & Architectural Verdict

**Primary Bottleneck: Network I/O (99.6% of execution time)**

- **Analysis:** Execution is overwhelmingly bound by sequential HTTP roundtrip latency. With 325 individual API calls averaging 550.5ms each, the program spends most of its time waiting on remote network packets.
- **Rust Viability Assessment:** A rewrite in Rust **will NOT significantly speed up execution** if sequential GitHub API calls remain unchanged. Rust cannot overcome external network roundtrip latency. At best, Rust could only optimize the remaining 0.4% (0.707s) of local compute.
- **High-Leverage Optimization Levers:**
  1. **Concurrent Request Batching:** Fetching blobs concurrently using `asyncio` / `httpx.AsyncClient` or worker pools would drastically reduce overall latency (estimated 5x–15x speedup).
  2. **Repository Tarball Streaming:** Using GitHub's single archive endpoint (`GET /repos/{owner}/{repo}/tarball`) downloads all files in 1 roundtrip, bypassing individual blob roundtrips entirely (estimated 10x–30x speedup).

---

## 5. Pure Local Compute Ceiling (In-Memory Baseline)

To evaluate Python's local compute speed in isolation (without remote network latency), a synthetic in-memory workload was benchmarked on this host:
- **In-Memory Processing Speed:** `616 files/s` (`24,832 lines/s`)
- **Time to classify & count 1,000 files locally:** `1.622s`
