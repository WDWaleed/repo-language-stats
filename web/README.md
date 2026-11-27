# Repo Language Stats — Web Dashboard & SVG Server

Next.js 15 dashboard and serverless SVG card API backed by Upstash Redis.

## Local Development

1. Copy `.env.example` to `.env.local` and fill in your Upstash Redis credentials:
   ```bash
   cp .env.example .env.local
   ```
2. Install dependencies and start the dev server:
   ```bash
   pnpm install
   pnpm dev
   ```
3. Run tests and production build:
   ```bash
   pnpm test
   pnpm build
   ```

## Deploying to Vercel

1. **Import Repository**: Connect this repository in the [Vercel Dashboard](https://vercel.com/new).
2. **Set Root Directory**: Set **Root Directory** to `web`.
3. **Framework Preset**: Next.js (auto-detected).
4. **Environment Variables**:
   - `UPSTASH_REDIS_REST_URL`: Your Upstash Redis REST URL.
   - `UPSTASH_REDIS_REST_TOKEN`: Your Upstash **Read-Only** REST token (recommended for public SVG/stats serving; if you enable on-demand refresh rate limiting, use a token with write access for `ratelimit:refresh:*`).
   - *(Optional for on-demand Refresh button)*:
     - `GITHUB_WORKFLOW_TOKEN`: GitHub PAT with `Actions: Read & write` permission.
     - `GITHUB_WORKFLOW_REPO`: `<owner>/<repo>` (e.g. `WDWaleed/repo-language-stats`).
     - `GITHUB_WORKFLOW_ID`: `sync-stats.yml`
     - `GITHUB_WORKFLOW_REF`: `main`
5. **Deploy**: Click **Deploy** and verify `https://<your-app>.vercel.app/api/health` returns `200 OK`.
