# Changelog

All notable changes to this project will be documented in this file.

## [0.1.0] — initial release

### Added
- **9 ATS adapters**: Greenhouse, Lever, Ashby, Workable, SmartRecruiters,
  Recruitee, Workday, RemoteOK, Hacker News "Who is Hiring?".
- **Editorial-press UI** (Search · Alerts · CV Match · Sources · Source Health).
  Server-rendered Jinja2 + HTMX (vendored locally), no build step. System fonts
  (zero CLS, zero font fetch). Dark mode via `prefers-color-scheme`.
- **Strong filtering**: keyword, company, location, work mode, level, degree,
  max YoE, languages, skills, posted-within, CV match threshold, sort order.
- **Local CV semantic match** (optional `[match]` extra) — upload PDF/DOCX/TXT,
  embedded with `sentence-transformers/all-MiniLM-L6-v2` on CPU, cosine-scored
  against every job. Nothing ever leaves the machine.
- **Saved searches + desktop alerts** — `notify-send` / `osascript` /
  PowerShell, deduplicated per-search so a job is only notified once.
- **Self-update scheduler** — APScheduler refreshes on a configurable interval
  in-process. No external cron.
- **In-UI source management** — add/remove ATS boards from `/sources` without
  editing YAML.
- **One-command launcher** — `jobhunt app` starts the server and opens the
  browser (auto-picks a free port if busy).
- **Standalone binaries** built with PyInstaller for Linux / macOS / Windows.
- **Docker support** — `docker compose up` with `127.0.0.1`-only binding.
- **Forward-only migrations** so the local DB upgrades across versions
  without losing data.
- **CSRF defence** — `Origin`/`Referer` check blocks malicious sites from
  POSTing to the running localhost server.
- **CSP + security headers** — `script-src 'self'`, `X-Frame-Options DENY`,
  `nosniff`, `Referrer-Policy same-origin`.
- **Linux desktop entry** — `packaging/install-desktop-entry.sh`.

### Tested
- 37 tests, all passing.
- CV pipeline verified end-to-end with three synthetic profiles (junior
  Python, senior ML, frontend React) — each ranked its expected role at #1.
- 30/30 random job URLs in the live DB resolve to real listings.
- Zero known CVEs across all dependencies (pip-audit clean).
