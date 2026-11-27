# repo-language-stats

[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![Code style: ruff](https://img.shields.io/badge/code%20style-ruff-000000.svg)](https://github.com/astral-sh/ruff)

A high-performance CLI tool to compute accurate, customizable programming language statistics across a GitHub user's entire portfolio of repositories or for an individual repository.

Unlike GitHub's built-in language bar, **repo-language-stats** provides dual metrics (physical line counts _and_ byte sizes), intelligently extracts executable code cells from Jupyter notebooks (ignoring markdown, outputs, and base64 plots), excludes noise and data files by default (like JSON, YAML, TOML, CSV, SVG, and dotenv), and allows full control over exclusions.

---

## Table of Contents

- [Features](#features)
- [Why repo-language-stats? (Comparison with GitHub)](#why-repo-language-stats-comparison-with-github)
- [Installation](#installation)
- [Authentication & Rate Limits](#authentication--rate-limits)
- [Usage & Examples](#usage--examples)
  - [Scan a Full GitHub User Account](#scan-a-full-github-user-account)
  - [Scan a Single Repository](#scan-a-single-repository)
  - [Scan a Local Repository](#scan-a-local-repository)
  - [Display Options (`--show-files`, `--per-repo`)](#display-options)
  - [Inclusion & Exclusion Flags (`--all`, `--include-*`)](#inclusion--exclusion-flags)
  - [Exporting Results (JSON, CSV, File Output)](#exporting-results)
  - [Benchmarking (`--benchmark`, `--synthetic-benchmark`)](#benchmarking)
- [CLI Reference](#cli-reference)
- [How It Works](#how-it-works)
- [Exclusions & Grouping Guide](#exclusions--grouping-guide)
- [Development & Testing](#development--testing)
- [License](#license)

---

## Features

- **Dual-Metric Line & Byte Counting**: Accurately counts non-binary file bytes and physical source code lines (`\n`), presenting percentage shares for both.
- **Jupyter Notebook Code Extraction**: Parses `.ipynb` notebooks via `nbformat`, extracting _only_ executable code cells. Strips markdown prose, cell execution outputs, and large base64-encoded plot images.
- **Single-Repo & User-Wide Scanning**: Scan all non-fork repositories for any GitHub username, or inspect a single repository via `owner/repo` positional syntax or `--repo <name>`.
- **Local Repository Scanning**: Scan any local repository or directory on disk instantly without network calls or tokens (`repo-language-stats .`), fully compatible with all exclusion filters and notebook parsing.
- **Sensible, Code-Centric Exclusions**: Data files, configs, and graphics (`.json`, `.jsonc`, `.csv`, `.yaml`, `.toml`, `.svg`, `.env*`) are filtered out by default so your language charts reflect actual source code rather than massive configuration manifests or datasets.
- **Unified Language Groupings**:
  - `.tsx` files are unified with TypeScript under **`TypeScript`**.
  - Python-kernel Jupyter notebooks (`.ipynb`) are unified with Python under **`Python`**.
- **Linguist-Compatible Classification**: Uses GitHub's canonical Linguist dataset (`languages.yml`, `vendor.yml`, and generated patterns) to accurately classify thousands of extensions and filenames.
- **Fast, Cloning-Free Discovery**: Leverages the GitHub Git Trees API (`recursive=1`) and Git Blobs API to inspect repository contents on the fly without running heavy `git clone` operations on disk.
- **Multiple Output Formats**: Beautiful interactive Rich terminal tables with ANSI colors, structured machine-readable JSON, or flat CSV for spreadsheet analysis.
- **Resilient API Handling**: Automatic exponential backoff with jitter on HTTP 403/429 rate limits, per-repo error isolation, and graceful handling of empty repositories (HTTP 409 Conflict).
- **Built-in Benchmarking**: `--benchmark` instruments every scan, separating network I/O time from local CPU computation time and saving a Markdown report to `docs/benchmarks/`. `--synthetic-benchmark` runs a pure in-memory workload (no network) to measure the local compute ceiling.

---

## Why repo-language-stats? (Comparison with GitHub)

GitHub's native language statistics bar has several known limitations. The table below outlines how `repo-language-stats` improves on them:

| Feature                          | GitHub Native Language Stats                                                   | repo-language-stats                                                                         |
| -------------------------------- | ------------------------------------------------------------------------------ | ------------------------------------------------------------------------------------------- |
| **Primary Metric**               | Source bytes only                                                              | **Both Source Bytes AND Physical Lines**                                                    |
| **Scan Scope**                   | Single repository only                                                         | **Entire User Portfolio OR Single Repository**                                              |
| **Jupyter Notebooks (`.ipynb`)** | Treats entire notebook as raw JSON; counts markdown, outputs, and base64 plots | **Extracts executable code cells only**; detects kernel language; strips outputs & markdown |
| **Data & Config Files**          | Counts JSON, YAML, TOML, SVG as code if classified                             | **Excluded by default** for clean code metrics (opt-in via `--all`)                         |
| **TypeScript & TSX**             | Often separated into distinct languages                                        | **Unified under TypeScript**                                                                |
| **Python & Notebooks**           | Often separated into Python vs Jupyter Notebook                                | **Unified under Python** for Python-kernel notebooks                                        |
| **Forked Repositories**          | Excluded completely                                                            | **Configurable** (excluded by default, toggleable via `--include-forks`)                    |
| **Custom Exclusions**            | Requires `.gitattributes` committed into repo                                  | **On-the-fly CLI flags** (`--exclude-pattern`, `--include-*`)                               |
| **Output Formats**               | Web UI progress bar only                                                       | **Rich terminal table, JSON, and CSV**                                                      |

---

## Installation

### Prerequisites

- Python 3.10 or newer.

### Using `uv` (Recommended)

You can install and run `repo-language-stats` instantly with [uv](https://docs.astral.sh/uv/):

```bash
# Run directly without installation
uvx --from git+https://github.com/WDWaleed/repo-language-stats repo-language-stats <username>

# Or install globally as a CLI tool
uv tool install git+https://github.com/WDWaleed/repo-language-stats
```

### Using `pip`

```bash
pip install git+https://github.com/WDWaleed/repo-language-stats
```

### From Local Source

```bash
git clone https://github.com/WDWaleed/repo-language-stats.git
cd repo-language-stats
uv sync

# Run using the full command or shorthand alias 'rls':
uv run repo-language-stats .
uv run rls .
```

---

## Authentication & Rate Limits

GitHub imposes rate limits on API requests:

- **Unauthenticated requests**: 60 requests per hour.
- **Authenticated requests**: 5,000 requests per hour.

For scanning multiple repositories or large codebases, providing a GitHub Personal Access Token (PAT) is strongly recommended. Only read access to public repositories is required (no write permissions needed).

### Supplying Your Token

**Option 1: `.env` File (Quickest)**

Add `GITHUB_TOKEN` to your `.env` file:
```env
GITHUB_TOKEN=ghp_yourPersonalAccessTokenHere
```
Then simply pass `--token` without needing to type your token:
```bash
repo-language-stats WDWaleed --token
```

**Option 2: Environment Variable**

```bash
# Linux / macOS (Bash / Zsh)
export GITHUB_TOKEN="ghp_yourPersonalAccessTokenHere"

# Windows (PowerShell)
$env:GITHUB_TOKEN="ghp_yourPersonalAccessTokenHere"

# Windows (Command Prompt)
set GITHUB_TOKEN=ghp_yourPersonalAccessTokenHere
```

**Option 3: Manual CLI Option**

```bash
repo-language-stats WDWaleed --token ghp_yourPersonalAccessTokenHere
```

---

## Usage & Examples

### Scan a Full GitHub User Account

Scans all public, non-fork repositories owned by the user:

```bash
repo-language-stats WDWaleed
```

### Scan a Single Repository

You can target an individual repository using `owner/repo` syntax, the `--repo` flag, or a full GitHub URL:

```bash
# Using owner/repo positional syntax:
repo-language-stats WDWaleed/repo-language-stats

# Using a full GitHub URL:
repo-language-stats https://github.com/WDWaleed/repo-language-stats

# Using the --repo flag:
repo-language-stats WDWaleed --repo repo-language-stats

# Scan a specific branch using --branch or -b:
repo-language-stats WDWaleed/repo-language-stats --branch develop
repo-language-stats WDWaleed/repo-language-stats -b feature/login

# Scan directly from a GitHub branch URL:
repo-language-stats https://github.com/WDWaleed/repo-language-stats/tree/develop

# Scan using ref syntax (@branch):
repo-language-stats WDWaleed/repo-language-stats@develop
```

### Scan a Local Repository

Scan a local directory on your filesystem without making any GitHub API calls or needing a token. Local paths are automatically detected, or you can pass `--local`:

```bash
# Scan current directory:
repo-language-stats .

# Scan a relative or absolute directory path:
repo-language-stats ./my-project
repo-language-stats ../other-repo
repo-language-stats /path/to/project

# Force local mode (useful if directory name matches a GitHub username):
repo-language-stats my-repo --local

# Scan all files on disk, ignoring .gitignore rules:
repo-language-stats . --no-gitignore
```

### Display Options

#### Show File Counts

Add the `--show-files` flag to display the total number of files counted for each language:

```bash
repo-language-stats WDWaleed --show-files
```

#### Per-Repository Breakdown

Add the `--per-repo` flag to display an individual language breakdown table for each scanned repository in addition to the aggregate summary:

```bash
repo-language-stats WDWaleed --per-repo
```

### Inclusion & Exclusion Flags

#### Include Default-Excluded Data & Config Files (`--all`)

By default, JSON, JSON with Comments, CSV, YAML, TOML, SVG, Dotenv, and TeX files are excluded to avoid skewing code stats. Use `--all` to include them:

```bash
repo-language-stats WDWaleed --all
```

#### Include Forked Repositories

```bash
repo-language-stats WDWaleed --include-forks
```

#### Include Private Repositories

Include private repositories owned by your account in the statistics (requires a GitHub token with `repo` scope for classic PAT or `Contents: Read` permission for fine-grained PAT; only works when scanning your own account):

```bash
repo-language-stats WDWaleed --include-private
```

#### Include Documentation, Vendored, or Generated Files

```bash
repo-language-stats WDWaleed --include-docs --include-vendored --include-generated
```

#### Exclude Custom Glob Patterns

Specify one or more custom exclusion patterns (matched against relative file paths and filenames):

```bash
repo-language-stats WDWaleed --exclude-pattern "tests/**" --exclude-pattern "*.min.js"
```

### Exporting Results

#### Export to JSON

```bash
# Output JSON to stdout:
repo-language-stats WDWaleed --format json

# Save JSON to a file:
repo-language-stats WDWaleed --format json -o stats.json
```

#### Export to CSV

```bash
# Output CSV to stdout:
repo-language-stats WDWaleed --format csv

# Save CSV to a file:
repo-language-stats WDWaleed --format csv -o stats.csv
```

#### Increase Verbosity for Debugging

```bash
repo-language-stats WDWaleed -v   # INFO logging
repo-language-stats WDWaleed -vv  # DEBUG logging (shows API endpoints, rate limit headers)
```

### Benchmarking

#### Profile a Real Scan (`--benchmark`)

Instruments the full scan pipeline — separating network I/O time from local CPU computation time — and writes a Markdown report to `docs/benchmarks/`:

```bash
# Benchmark a full user profile:
repo-language-stats WDWaleed --benchmark --token

# Benchmark a single repository:
repo-language-stats WDWaleed/repo-language-stats --benchmark --token
```

Report routing:
- `WDWaleed/repo-language-stats` → `docs/benchmarks/demo_repo.md` (overwrite)
- `WDWaleed` → `docs/benchmarks/demo_profile.md` (overwrite)
- Any other target → `docs/benchmarks/others.md` (append; gitignored)

#### Pure CPU Synthetic Benchmark (`--synthetic-benchmark`)

Runs an in-memory workload with no network calls, measuring only local computation speed. Useful for assessing how much time is actually spent on CPU work vs. waiting for the network:

```bash
repo-language-stats --synthetic-benchmark
```

---

## CLI Reference

> **Tip:** You can use `rls` as a shorthand alias anywhere instead of `repo-language-stats` (e.g. `uv run rls .` or `rls WDWaleed`).

```
usage: repo-language-stats [-h] [--repo REPO] [-b BRANCH] [--token [TOKEN]]
                           [--include-forks] [--include-private]
                           [--include-generated] [--include-vendored]
                           [--include-docs] [--all]
                           [--exclude-pattern EXCLUDE_PATTERNS] [--per-repo]
                           [--show-files] [--format {table,json,csv}]
                           [-o OUTPUT] [--ipynb-language IPYNB_LANGUAGE]
                           [--local] [--no-gitignore] [--benchmark]
                           [--synthetic-benchmark] [-v]
                           [TARGET]
```

### Arguments & Options

| Option                      | Description                                                                                                                                                                                                          |
| --------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `TARGET`                    | GitHub username (e.g. `WDWaleed`), repository in `owner/repo` format, GitHub URL, or local directory path (e.g. `.` or `/path/to/project`).                                                                           |
| `--local`                   | Force treat `TARGET` as a local directory path rather than a GitHub username or repository.                                                                                                                           |
| `--no-gitignore`            | Do not respect `.gitignore` rules during local scans; scan all files on disk (excluding `.git/`).                                                                                                                    |
| `--repo REPO`               | Specific repository name to scan when `TARGET` is a username.                                                                                                                                                        |
| `-b, --branch BRANCH`       | Specific branch or Git ref to scan (single repository mode only; defaults to repository's default branch).                                                                                                           |
| `--token [TOKEN]`           | GitHub personal access token (if passed without a value, automatically uses `GITHUB_TOKEN` from `.env`; defaults to `GITHUB_TOKEN` environment variable).                                                            |
| `--include-forks`           | Include forked repositories in the scan (excluded by default).                                                                                                                                                       |
| `--include-private`         | Include private repositories (requires a token with `repo` scope; only works when scanning your own account).                                                                                                        |
| `--include-generated`       | Include generated, minified, and lock files (e.g. `*.min.js`, `package-lock.json`).                                                                                                                                  |
| `--include-vendored`        | Include vendored dependencies (e.g. `vendor/`, `node_modules/`).                                                                                                                                                     |
| `--include-docs`            | Include documentation and prose files (`.md`, `.rst`, `.txt`).                                                                                                                                                       |
| `--all`                     | Include data, configuration, and TeX files excluded by default (`.json`, `.jsonc`, `.csv`, `.yaml`, `.toml`, `.svg`, `.env*`, `.tex`).                                                                             |
| `--exclude-pattern PATTERN` | Glob pattern for paths or filenames to exclude (can be specified multiple times).                                                                                                                                    |
| `--per-repo`                | Display per-repository breakdown tables in addition to the aggregate summary.                                                                                                                                        |
| `--show-files`              | Include a **Files** count column in the output table.                                                                                                                                                                |
| `--format {table,json,csv}` | Output format: `table` (default), `json`, or `csv`.                                                                                                                                                                  |
| `-o, --output OUTPUT`       | Write output to the specified file path instead of stdout.                                                                                                                                                           |
| `--ipynb-language LANG`     | Override language for Jupyter notebooks whose kernel cannot be auto-detected.                                                                                                                                        |
| `-v, --verbose`             | Increase logging verbosity (`-v` for INFO, `-vv` for DEBUG).                                                                                                                                                         |
| `--benchmark`               | Instrument the full scan and save a Markdown timing report to `docs/benchmarks/` (separates network I/O time from local CPU time).                                                                                   |
| `--synthetic-benchmark`     | Run a pure in-memory CPU benchmark (no network) and print the results. `TARGET` is not required when this flag is set.                                                                                               |
| `-h, --help`                | Show help message and exit.                                                                                                                                                                                          |

---

## How It Works

```
GitHub API (User / Repo)
         │
         ▼
List Repositories (exclude forks by default)
         │
         ▼
Git Trees API (recursive=1, no cloning)
         │
         ▼
Tree Discovery & Exclusions:
  ├── Binary file check (extension & null-byte inspection)
  ├── Vendored paths (vendor.yml / node_modules)
  ├── Generated patterns (minified, lockfiles)
  ├── Documentation check (.md, .rst, .txt)
  ├── Default data exclusions (.json, .csv, .yaml, .toml, .svg, .env, .tex)
  └── Custom --exclude-pattern globs
         │
         ▼
Content Fetch (Git Blobs API)
         │
  ├── Normal Source File ──> Linguist Classifier (.tsx -> TypeScript) ──> Count bytes & lines
  └── Jupyter Notebook (.ipynb) ──> Extract code cells only ──> Count bytes & lines
         │
         ▼
Metric Aggregation (per-repo & user-wide totals)
         │
         ▼
Rich Table / JSON / CSV Report
```

1. **Repository Listing**: Fetches repository metadata for the target user (or single repo), tracking default branches.
2. **Tree Discovery**: Uses GitHub's Git Trees API to fetch the complete file hierarchy in a single API request per repository without cloning gigabytes of data.
3. **Filtering**: Applies multi-stage exclusion rules (binary detection, vendored libraries, generated assets, documentation, and default data exclusions).
4. **Blob Fetching & Parsing**: Downloads eligible source files and notebook blobs via the GitHub Git Blobs API.
5. **Notebook Extraction**: Parses Jupyter notebooks using `nbformat`, inspecting the `metadata.kernelspec` or language metadata to detect the language (falling back to Python), extracts only executable code cells, and computes exact code bytes and lines.
6. **Language Classification**: Matches file extensions and filenames against the vendored GitHub Linguist definitions, applying canonical groupings (e.g., `.tsx` $\rightarrow$ `TypeScript`).
7. **Reporting**: Aggregates metrics into per-language byte, line, and file sums with computed percentages, rendering the results into Rich tables, JSON, or CSV.

---

## Exclusions & Grouping Guide

For an in-depth reference on excluded formats, why they are filtered out by default, and how language groupings work, see:

- [docs/excluded.md](docs/excluded.md)

---

## Web Dashboard & Embeddable SVG Cards

In addition to the CLI, this repository includes a Next.js 15 web dashboard and serverless SVG card API in [`web/`](web/README.md) backed by Upstash Redis and a scheduled GitHub Actions sync worker.

### Card Layouts

| Card Type | Dimensions | Default `langs_count` | Sample |
|---|---|---|---|
| `bar` | `495 × dynamic` | all languages with ≥ 1% share | ![Bar Card](docs/sample_bar_light.svg) |
| `breakdown` | `520 × dynamic` | `10` | ![Breakdown Card](docs/sample_breakdown.svg) |
| `donut` | `495 × 220` | `6` | ![Donut Card](docs/sample_donut.svg) |
| `compact` | `495 × 32` | `4` | ![Compact Card](docs/sample_compact.svg) |

### SVG Endpoint & Query Parameters

```
GET /api/svg/<username>/<card_type>?theme=auto&metric=bytes
```

| Parameter | Default | Valid Values | Notes |
|---|---|---|---|
| `theme` | `light` | `light`, `dark`, `auto` | `auto` embeds `@media (prefers-color-scheme: dark)` CSS variables |
| `metric` | `bytes` | `bytes`, `lines`, `both` | `both` is supported on `breakdown` cards |
| `langs_count` | varies | `1`–`50` | `bar`: omit to show all languages with ≥ 1% share (recommended); explicit value caps at that number. `breakdown` `10`, `donut` `6`, `compact` `4` |
| `show_files` | `false` | `true`, `false` | Shows the **Files** column on `breakdown` cards |
| `hide_title` | `false` | `true`, `false` | Hides the card title header (not applicable to `compact`) |
| `title` | auto | any string | Custom card title (XML-escaped) |

### Embedding in Your GitHub Profile README

**Markdown (`auto` theme):**
```markdown
![Top Languages](https://<your-app>.vercel.app/api/svg/<username>/bar?theme=auto)
```

**HTML `<picture>` (explicit GitHub Light / Dark switching):**
```html
<picture>
  <source
    media="(prefers-color-scheme: dark)"
    srcset="https://<your-app>.vercel.app/api/svg/<username>/bar?theme=dark"
  />
  <source
    media="(prefers-color-scheme: light)"
    srcset="https://<your-app>.vercel.app/api/svg/<username>/bar?theme=light"
  />
  <img
    alt="Top Languages"
    src="https://<your-app>.vercel.app/api/svg/<username>/bar?theme=light"
  />
</picture>
```

For architecture, Upstash Redis key schemas, and worker setup, see:
- [docs/web_architecture.md](docs/web_architecture.md)
- [docs/worker_setup.md](docs/worker_setup.md)
- [web/README.md](web/README.md)

---

## Development & Testing

### Setting Up Development Environment

```bash
git clone https://github.com/WDWaleed/repo-language-stats.git
cd repo-language-stats
uv sync
```

### Running Tests

Run the full pytest suite:

```bash
uv run pytest
```

### Running Test Coverage

Run tests with line and branch coverage reporting:

```bash
uv run pytest --cov=repo_language_stats --cov-branch --cov-report=term-missing
```

### Building Distribution Packages

Build wheel and source distributions using `uv`:

```bash
uv build
```

---

## License

This project is licensed under the MIT License. See [LICENSE](LICENSE) for details.
