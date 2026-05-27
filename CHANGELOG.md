# Changelog

All notable changes to this project will be documented in this file.

## [Unreleased]

### Added
- **5 new job sources**: SimplifyJobs (internships + new-grad), Arbeitnow
  (EU tech), Jobicy (remote + salary data), Himalayas (remote + rich fields),
  The Muse (US tech with structured levels). Total: 14 adapters, 38 boards.
- **Employment type filter** in sidebar with facet counts (Full-time,
  Part-time, Contract, Internship).
- **Salary filter** — min salary input in sidebar, salary badges on job cards.
- **Salary extraction** from Ashby (compensation API), RemoteOK, Jobicy,
  Himalayas — displayed as formatted ranges ($120,000–$180,000 USD).
- **`jobhunt update` command** — one-command self-update via uv or pipx.
- **`uv tool install` distribution** — replaces PyInstaller binaries as the
  primary install method. One-line install scripts for Linux/macOS/Windows.
- **Employment type normalization** — 33+ raw variants collapsed into 5 clean
  categories. German Arbeitnow labels (berufserfahren, Werkstudent, etc.)
  mapped correctly.
- **German internship detection** — Praktikant, Werkstudent, Berufseinstieg
  recognized in title/description extraction.
- **16 new tests** (53 total) — employment type normalization, remote
  detection accuracy, German pattern matching.

### Changed
- **Default CLI behavior**: `jobhunt` with no arguments now launches the app
  (starts server + opens browser) instead of showing help.
- **Pagination caps raised**: SmartRecruiters 200→1000, Workday 20→500,
  Workable 50→500.
- **Remote detection improved**: strong patterns (fully-remote, remote-first,
  WFH) match anywhere; bare "remote" only matches in title + first 300 chars
  to reduce false positives.
- **Company names** now display correctly — ATS board slugs replaced by proper
  names from sources.yaml; aggregator per-job names flow through.
- **Structured API data preferred** over regex heuristics for remote status,
  employment type, and salary when the source provides it.

### Fixed
- SimplifyJobs and Arbeitnow `remote_structured` and `employment_type` were
  stored in `extra` dict instead of RawJob fields — never reached the DB.
- Ashby salary floor of $0 was silently dropped by a falsy `or` check.
- The Muse pagination stopped after first page when `page_count` was 0.
- SmartRecruiters detail 404 for one posting killed the entire board scrape.
- Workday detail endpoint only caught ValueError/TypeError, not network errors.
- Salary data was cleared on job update when the new scrape had no salary.
- Lever scraper crashed on non-list API responses.
- 12 dead source slugs removed or corrected (companies changed ATS platforms).

### Removed
- Internal research/dev HTML files from the tracked repo.
- Redundant `install-from-source.sh` / `.ps1` scripts (merged into main
  install scripts).

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
- **One-command launcher** — `jobhunt` starts the server and opens the
  browser (auto-picks a free port if busy).
- **Docker support** — `docker compose up` with `127.0.0.1`-only binding.
- **Forward-only migrations** so the local DB upgrades across versions
  without losing data.
- **CSRF defence** — `Origin`/`Referer` check blocks malicious sites from
  POSTing to the running localhost server.
- **CSP + security headers** — `script-src 'self'`, `X-Frame-Options DENY`,
  `nosniff`, `Referrer-Policy same-origin`.

### Tested
- 53 tests, all passing.
- CV pipeline verified end-to-end with three synthetic profiles (junior
  Python, senior ML, frontend React) — each ranked its expected role at #1.
- 11,388 jobs scraped from 38 sources with zero errors.
- All filters verified: remote, level, employment type, salary, keyword,
  company, location, languages, skills, posted-within, multi-filter combos.
- All queries <120ms at 11k jobs.
- Zero known CVEs across all dependencies (pip-audit clean).
