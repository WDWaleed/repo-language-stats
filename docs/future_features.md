# Future Features

Planned features and enhancements for `repo-language-stats`.

---

## Done

- **Private Repository Scanning** — Scan private repositories owned by the authenticated user in addition to public ones using `--include-private`. Requires a GitHub token with appropriate scopes (`repo` for classic PAT or `Contents: Read` for fine-grained PAT). See [docs/private_repo_count.md](private_repo_count.md) for design details.

---

## Planned

- **GitHub Token should be used automatically** whenever available in .env. The --token flag should suffice instead of manually entering the value

- **Web Dashboard & SVG Cards** — A self-hosted FastAPI + Next.js web service that periodically scans repositories, generates embeddable SVG language stat cards (bar chart, breakdown table, donut chart), and serves them at stable URLs for use in GitHub profile READMEs.

- **Local Repository Scanning** — Analyse a local Git repository on disk without making any API calls, using the working tree directly.

- **Language Ignore List** — Allow users to specify languages to exclude from results (e.g., `--ignore-language Shell`), complementing the existing file-level exclusion flags.
