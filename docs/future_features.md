# Future Features

Planned features and enhancements for `repo-language-stats`.

---

## Done

- **Private Repository Scanning** — Scan private repositories owned by the authenticated user in addition to public ones using `--include-private`. Requires a GitHub token with appropriate scopes (`repo` for classic PAT or `Contents: Read` for fine-grained PAT). See [docs/private_repo_count.md](private_repo_count.md) for design details.

- **Automatic GitHub Token from `.env`** — GitHub Token is used automatically whenever available in `.env` when `--token` is passed without an explicit argument or via the `GITHUB_TOKEN` environment variable.

- **Branch Selection** — Analyze a specific Git branch or ref instead of only the default branch using `--branch <name>` or `-b <name>`. Also automatically detects branches from GitHub URLs (`/tree/<branch>`) and ref syntax (`owner/repo@<branch>`).

---

## Planned

- **Web Dashboard & SVG Cards** — A self-hosted FastAPI + Next.js web service that periodically scans repositories, generates embeddable SVG language stat cards (bar chart, breakdown table, donut chart), and serves them at stable URLs for use in GitHub profile READMEs.

- **Local Repository Scanning** — Analyse a local Git repository on disk without making any API calls, using the working tree directly.

- **Language Ignore List** — Allow users to specify languages to exclude from results (e.g., `--ignore-language Shell`), complementing the existing file-level exclusion flags.

- **Benchmarking** — Added `--benchmark` and `--synthetic-benchmark` flags. `--benchmark` instruments the full scan pipeline, separating network I/O time from local CPU computation time, tracking wire payload sizes and effective bandwidth, and writing a Markdown report to `docs/benchmarks/`. `--synthetic-benchmark` runs a pure in-memory CPU workload (no network) to establish a local compute ceiling — useful for assessing whether a Rust rewrite would yield meaningful gains. See [docs/benchmarks/](benchmarks/) for real benchmark results.
