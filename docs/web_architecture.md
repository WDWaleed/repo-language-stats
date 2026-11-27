# Web Dashboard & Serverless SVG Architecture

## Overview

The web layer decouples **repository scanning** (long-running, authenticated) from **SVG card serving** (fast, cached, read-only):

1. **Background Sync Worker ([`.github/workflows/sync-stats.yml`](../.github/workflows/sync-stats.yml))**
   - Runs every 6 hours (`0 */6 * * *`) or on-demand via `workflow_dispatch`.
   - Executes `uv run rls <username> --format json --include-private --show-files` and pipes the aggregate JSON to [`scripts/push_to_upstash.py`](../scripts/push_to_upstash.py).
   - Injects Linguist hex colors (`src/repo_language_stats/svg/utils.py`) and writes the payload to Upstash Redis under `stats:<username>`.
   - Strictly omits `--per-repo` so private repository names and file paths are never stored or exposed.

2. **Upstash Redis Store**
   - `stats:<username>` — `CachedUserStats` JSON payload (aggregate language bytes, lines, files, percentages, colors, `last_scanned`).
   - `ratelimit:refresh:<username>` — 600-second (`10m`) cooldown lock for on-demand refresh dispatches.

3. **Next.js 15 App & Serverless API (`web/`)**
   - `GET /api/svg/[username]/[card_type]` — Renders `bar`, `breakdown`, `donut`, or `compact` SVGs via the TypeScript SVG engine ([`web/src/lib/svg/`](../web/src/lib/svg/)), returning `Content-Type: image/svg+xml; charset=utf-8`, SHA-256 `ETag` (`304 Not Modified` support), and `Cache-Control: public, max-age=14400, s-maxage=14400, stale-while-revalidate=3600`. Uncached users receive a `200 OK` fallback SVG card.
   - `GET /api/stats/[username]` — Returns cached JSON stats (`404` if missing).
   - `POST /api/stats/[username]/refresh` — Enforces `ratelimit:refresh:<username>` and dispatches `sync-stats.yml` via GitHub Actions API (`202 Accepted` or `429 Too Many Requests`).
   - `GET /api/health` — Verifies Upstash Redis connectivity (`PONG`).
   - Interactive dashboard (`/` and `/[username]`) with live card preview, theme/metric controls, Markdown/HTML/`<picture>` snippet generator, sortable table, and refresh button.
