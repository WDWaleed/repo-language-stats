# Background Worker & Upstash Sync Setup

This guide covers configuring GitHub Actions and Upstash Redis to automatically scan your repositories (including private repositories) and push aggregate language statistics to Upstash Redis every 6 hours.

---

## 1. Create a GitHub Personal Access Token (`SCANNER_GITHUB_TOKEN`)

The default `GITHUB_TOKEN` provided by GitHub Actions only has access to the repository running the workflow. To scan all your public and private repositories:

### Option A — Fine-grained PAT (Recommended)
1. Go to **GitHub → Settings → Developer settings → Personal access tokens → Fine-grained tokens**.
2. Click **Generate new token**.
3. Set **Repository access** to **All repositories**.
4. Under **Repository permissions**, grant **Contents: Read-only** and **Metadata: Read-only**.
5. Copy the generated token.

### Option B — Classic PAT
1. Go to **GitHub → Settings → Developer settings → Personal access tokens → Tokens (classic)**.
2. Click **Generate new token (classic)**.
3. Select the **`repo`** scope (required for private repository access).
4. Copy the generated token.

---

## 2. Create an Upstash Redis Database

1. Log in to the [Upstash Console](https://console.upstash.com/) and create a Redis database.
2. Open the database details page and copy:
   - **`UPSTASH_REDIS_REST_URL`** (e.g. `https://<db-name>.upstash.io`)
   - **`UPSTASH_REDIS_REST_TOKEN`** (the Read/Write REST token for the background worker)

---

## 3. Add GitHub Repository Secrets

In your repository on GitHub, go to **Settings → Secrets and variables → Actions → New repository secret** and add:

| Secret Name | Value |
|---|---|
| `SCANNER_GITHUB_TOKEN` | Your GitHub PAT from Step 1 |
| `UPSTASH_REDIS_REST_URL` | Your Upstash REST URL from Step 2 |
| `UPSTASH_REDIS_REST_TOKEN` | Your Upstash Read/Write REST token from Step 2 |

> **Security note:** The workflow passes `--include-private` and strictly omits `--per-repo`, so private repository names and directory structures are never stored in Redis or exposed in SVG cards.

---

## 4. Test & Verify

### Local Dry-Run / Live Sync
```bash
# Dry-run (prints payload without writing to Upstash)
uv run --env-file .env rls <username> --format json --include-private --show-files \
  | uv run python scripts/push_to_upstash.py --username <username> --dry-run

# Live sync (writes stats:<username> to Upstash)
uv run --env-file .env rls <username> --format json --include-private --show-files \
  | uv run python scripts/push_to_upstash.py --username <username>
```

### GitHub Actions Dispatch
1. Go to the **Actions** tab in your repository.
2. Select **Sync Language Stats to Upstash**.
3. Click **Run workflow**.
4. Confirm `stats:<username>` appears in your Upstash Redis Data Browser.
