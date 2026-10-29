# File Exclusions and Language Grouping Guide

This document describes the default exclusion policy, configuration options, and language grouping rules used by `repo-language-stats` when scanning GitHub repositories.

---

## 1. Files Excluded by Default

To provide meaningful programming-language statistics that reflect actual application source code, `repo-language-stats` excludes data, asset, and environment configuration files by default.

### Default Excluded File Types

| Category | File Extensions / Patterns | Description |
|---|---|---|
| **JSON** | `.json`, `.jsonl`, `.json5`, `.jsonld` | Structured data exchanges, lockfiles, API payloads |
| **JSON with Comments** | `.jsonc`, `tsconfig.json`, `jsconfig.json`, `.code-workspace` | Configuration files supporting comments |
| **CSV** | `.csv` | Tabular data exports and datasets |
| **YAML** | `.yaml`, `.yml` | Serialization manifests, CI/CD pipelines, configurations |
| **TOML** | `.toml` | Configuration manifests (e.g., `pyproject.toml`, `Cargo.toml`) |
| **SVG** | `.svg` | Scalable Vector Graphics images (XML-based vector assets) |
| **Dotenv** | `.env`, `.env.*`, `*.env` | Local environment variables and configuration files |

### Why Are These Excluded by Default?

1. **Volume Disproportion**: Large data files (such as multi-megabyte `.json`/`.csv` datasets or `.yaml` fixtures) and graphic assets (like `.svg` icon sets) frequently dwarf actual programming logic in byte and line counts.
2. **Configuration vs Code**: Files like `.json`, `.jsonc`, `.toml`, `.yaml`, and `.env` contain serialized configuration, schemas, and metadata rather than executable programming logic.
3. **Accuracy**: Excluding these formats by default gives a clean, developer-centric view of the programming languages powering a repository.

---

## 2. Including Default Excluded Files (`--all`)

If you want to count all files—including JSON data, JSON with Comments configs, CSV datasets, YAML configs, TOML manifests, SVG assets, and dotenv files—use the **`--all`** flag:

```bash
repo-language-stats <username> --all
```

*Example:*
```bash
uv run repo-language-stats octocat --all
```

When `--all` is supplied, files matching `.json`, `.jsonc`, `.csv`, `.yaml`, `.yml`, `.toml`, `.svg`, and `.env*` will be classified according to GitHub Linguist rules (e.g. `JSON`, `JSON with Comments`, `CSV`, `YAML`, `TOML`, `SVG`, `Dotenv`) and included in the byte, line, and file count statistics.

---

## 3. Other Exclusions and Inclusion Flags

| Category | Default Behavior | Flag to Include | Description |
|---|---|---|---|
| **Binary files** | Excluded | *(Always excluded)* | Images, audio, video, archives, compiled binaries (`.png`, `.jpg`, `.exe`, `.dll`, `.zip`, `.pdf`, etc.) and files with null bytes |
| **Vendored paths** | Excluded | `--include-vendored` | Third-party dependencies matched by Linguist rules (`vendor/`, `node_modules/`, `third_party/`, etc.) |
| **Generated files** | Excluded | `--include-generated` | Auto-generated code (`*.min.js`, `*.pb.go`, `package-lock.json`, `poetry.lock`, etc.) |
| **Documentation** | Excluded | `--include-docs` | Prose files (`.md`, `.rst`, `.txt`, `.adoc`) |
| **Custom globs** | None | `--exclude-pattern GLOB` | Custom exclusion glob pattern (can be passed multiple times) |

*Example combining flags:*
```bash
uv run repo-language-stats octocat --all --include-docs --include-vendored
```

---

## 4. Language Grouping Rules

To keep statistics cohesive and avoid splitting unified ecosystems into separate rows:

### TypeScript & TSX
- Files with the `.tsx` extension are unified with TypeScript under **`TypeScript`**.
- Both `.ts` and `.tsx` source bytes, lines, and file counts accumulate together under `TypeScript`.

### Python & Jupyter Notebooks
- Code cells extracted from Jupyter notebooks (`.ipynb`) using a Python kernel are counted together with standard `.py` files under **`Python`**.
- Notebook markdown cells, outputs, and execution metadata continue to be excluded.
- Notebooks running non-Python kernels (e.g. R, Julia) remain attributed to their respective languages (e.g. `Jupyter (R)`).

