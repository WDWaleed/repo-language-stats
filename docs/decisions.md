# Architectural & Design Decisions

This document records fixed architectural and design decisions for `repo-language-stats` and its web dashboard / SVG rendering server.

---

| ID | Date | Decision | Rationale |
|---|---|---|---|
| **D1** | 2026-11-26 | **Python SVG Engine:** Implemented with `jinja2` templates + helper module `repo_language_stats.svg`. | Avoids heavy native graphical dependencies (`cairosvg`, `matplotlib`, `pillow`) keeping CLI installs lightweight and cross-platform. |
| **D2** | 2026-11-26 | **Next.js Stack:** Next.js 15 (App Router), React 19, TypeScript, Tailwind CSS v4, Lucide React icons, `@upstash/redis`. Package manager: `pnpm`. | Modern standard for Vercel deployment with sub-15ms serverless cold starts and zero hosting cost. |
| **D3** | 2026-11-26 | **Card Dimensions:** `bar`: 495 × dynamic (based on legend rows); `breakdown`: 520 × dynamic; `donut`: 495 × 220; `compact`: 495 × 32. | Standard GitHub README column width (495–520px) ensuring no horizontal overflow or scrollbars. |
| **D4** | 2026-11-26 | **Themes:** `light` (`#ffffff` bg, `#24292f` text, `#d0d7de` border), `dark` (`#0d1117` bg, `#e6edf3` text, `#30363d` border), `auto` (embeds `@media (prefers-color-scheme: dark)` CSS variables directly inside `<svg><style>`). | GitHub's Camo proxy preserves SVG internal CSS `@media` queries, providing native dark/light mode switching without two separate images. |
| **D5** | 2026-11-26 | **Upstash Redis Key Convention:** Key `stats:{username}` stores the complete AggregateStats JSON; Key `ratelimit:refresh:{username}` with 600s TTL enforces 1 refresh per 10 minutes. | Sub-10ms REST fetches; prevents GitHub Actions quota exhaustion. |
| **D6** | 2026-11-26 | **Caching Headers for Camo:** `Cache-Control: public, max-age=14400, s-maxage=14400, stale-while-revalidate=3600` + SHA-256 `ETag`. Supports `304 Not Modified`. | Balances freshness (updates within ~4 hours) with CDN caching and GitHub Camo compatibility. |
| **D7** | 2026-11-26 | **Error Handling in SVGs:** If user stats are not found in Redis, return an SVG card stating *"User not scanned yet. Visit dashboard to sync"* with HTTP 200 rather than HTTP 404/500. | Prevents ugly broken image icons from displaying in GitHub profile READMEs when a user has not been scanned yet. |
| **D8** | 2026-11-26 | **Private Repo Privacy:** The sync worker passes `--include-private` but strictly omits `--per-repo`. Private repository names and directory structures are never saved to Redis or rendered into SVGs. | Guarantees complete confidentiality for private codebases while allowing accurate overall language totals. |
