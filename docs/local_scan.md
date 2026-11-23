# Local Repository Scanning

`repo-language-stats` supports scanning local repositories and directories directly from disk. This mode performs all language classification, byte and line counting, exclusion filtering, and notebook parsing locally without making GitHub API requests or requiring authentication tokens.

---

## Usage

You can scan a local directory by passing a path as the `TARGET` argument. Relative paths, absolute paths, and current working directory (`.`) are automatically detected:

```bash
# Scan current working directory
repo-language-stats .

# Scan a relative directory path
repo-language-stats ./my-project
repo-language-stats ../other-repo

# Scan an absolute directory path
repo-language-stats /home/user/projects/repo-language-stats
repo-language-stats "C:\Users\User\Projects\repo-language-stats"

# Force local interpretation with --local (useful if folder matches a username)
repo-language-stats my-repo --local
```

---

## How It Works

1. **Target Detection**: When `TARGET` exists as a directory on disk, or when `--local` is provided, `repo-language-stats` routes the scan to `local_scanner.py` instead of the GitHub REST API client.
2. **Directory Traversal**: The scanner walks the directory tree recursively. The `.git/` directory and all internal Git metadata are automatically excluded from the scan.
3. **Filtering**: The existing Linguist-based file discovery filter (`filter_tree`) applies identical exclusion rules:
   - Binaries are detected and skipped.
   - Vendored dependencies (e.g. `node_modules/`, `vendor/`) are excluded (unless `--include-vendored` is passed).
   - Generated files and lockfiles (e.g. `package-lock.json`, `*.min.js`) are excluded (unless `--include-generated` is passed).
   - Documentation and prose files (`.md`, `.rst`, `.txt`) are excluded by default (unless `--include-docs` is passed).
   - Data formats (`.json`, `.yaml`, `.csv`, `.toml`, `.svg`, `.env`) are excluded by default (unless `--all` is passed).
   - Custom exclusion patterns via `--exclude-pattern` are honored.
4. **Content Analysis**: Files are read directly from the filesystem:
   - Jupyter notebooks (`.ipynb`) are parsed with `nbformat` to extract executable code cells.
   - Source code files are classified with GitHub Linguist rules and measured for bytes and physical lines.
5. **Reporting**: Results are aggregated and rendered using standard output formatters (terminal table, JSON, or CSV).

---

## Flag Compatibility

All standard reporting and filtering flags work with local scanning:

| Supported Flags | Incompatible Flags (Error) |
| --- | --- |
| `--format {table,json,csv}` | `--repo` (single repo is already specified by path) |
| `-o, --output` | `--branch` (local scans analyze the current checked-out working tree) |
| `--show-files` | `--include-private` (meaningless without GitHub API) |
| `--per-repo` | `--include-forks` (meaningless for local folder) |
| `--include-docs` | |
| `--include-vendored` | |
| `--include-generated` | |
| `--all` | |
| `--exclude-pattern` | |
| `--ipynb-language` | |
| `--benchmark` | |

---

## Benchmarking Local Repositories

Passing `--benchmark` with a local target measures real CPU execution time on disk without any network latency:

```bash
repo-language-stats . --benchmark
```

In the benchmark diagnostics table and generated markdown report, Network I/O time will be `0.0s` (0 requests), and the report reflects the pure file reading, classification, and counting throughput on your local hardware.
