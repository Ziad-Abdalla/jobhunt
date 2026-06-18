# Changelog

## [0.13.2] — 2026-06-19

### Added
- **First-run setup prompt.** When a key or your location is missing, a friendly
  modal walks you through it — location, Reed key (with a "Get a free key" link),
  optional Jooble key — then saves and live-tests them. Pre-fills existing values
  so it never erases a saved key; dismissable with "Maybe later".

### Fixed
- **Update check + update now work from GitHub tags, not stale PyPI.** The check
  compares versions numerically (so v0.13.2 correctly beats v0.9.2) and the
  in-app update reinstalls from the matching tag. Degrades gracefully when the
  repo isn't publicly reachable.

## [0.13.1] — 2026-06-19

### Fixed
- **Zero-experience local jobs are no longer mislabelled "mid".** An unqualified
  non-tech title (Cleaner, Catering Assistant) now defaults to **entry**, so the
  0-experience / entry filter actually finds local work. Tech titles still
  default to mid by convention.

### Added / Changed
- **Refresh no longer hangs.** The Refresh button starts the scrape in the
  background and returns instantly; it polls `/api/refresh/status` for live
  progress while the rest of the app stays usable.
- **Faster refresh.** Source concurrency 4 → 8 and Reed depth 500 → 300 per
  keyword (~40% less work, still thousands of jobs after dedup). No data dropped.
- **Gentler stale window (14 → 30 days).** Active listings are re-seen on every
  scrape and never expire; this only widens the grace period for jobs a refresh
  temporarily misses.

## [0.13.0] — 2026-06-18

### Added
- **Reed searches are now "near me".** When you set a home location, every
  Reed search is scoped to that town plus a travel radius
  (`JOBHUNT_REED_DISTANCE_MILES`, default 15) using Reed's server-side
  distance filter — so results are jobs you can actually reach rather than
  UK-wide. With no location set, Reed stays UK-wide as before.
- **More London early-career coverage.** Added verified London-heavy boards
  (Palantir, Wayve, Synthesia, GoHenry, Pleo) and weekend / part-time Reed
  searches (weekend, part time, saturday, barista, sales assistant) for
  study-friendly local work.

### Fixed
- **Jooble no longer returns the wrong London.** A bare "London" resolved to
  London, Kentucky; UK searches now name the country. Jooble's free API is
  UK-wide and coarsely located, so granular "near me" results come from Reed
  (key) and the company boards.

### Changed
- Trimmed off-target Jooble country searches (Egypt, Cairo, Australia) and
  added UK intern / graduate / placement searches.

## [0.12.0] — 2026-05-29

### Removed
- **Bug Bounty section removed.** The `/bounties` page, the per-platform
  program parsers (`bounties.py`), the “Bug Bounty” nav tab, the
  `/api/refresh-bounties` endpoint, and the bounty fetch inside
  `/api/refresh` are all gone — along with their tests and the bounty
  references in the README, CLAUDE.md, and MAINTENANCE.md. jobhunt now
  focuses on its three job sections: **Jobs**, **Local Jobs**, and
  **Freelance**.

## [0.11.2] — 2026-05-28

### Security
- **Backup zips no longer leak API keys.** v0.11.0's `jobhunt backup`
  serialised the `.env` file verbatim, including `JOOBLE_API_KEY` and
  `REED_API_KEY`. A user emailing a backup for support or syncing it
  to cloud storage would have leaked live credentials. Now API key
  values are redacted by default with a sentinel value; opt back in
  with `--include-secrets` (which prints a stderr warning).
- **`jobhunt restore` allowlists env keys and source kinds.** A
  hostile backup file could previously have injected arbitrary
  `JOBHUNT_*` environment variables on restore. Now only
  `JOBHUNT_JOOBLE_API_KEY`, `JOBHUNT_REED_API_KEY`, and
  `JOBHUNT_USER_LOCATION` survive — everything else is filtered.
  Likewise `local_sources.yaml` is now `safe_load`'d, schema-checked,
  and entries whose `source` isn't a known scraper kind are dropped
  with a stderr warning.
- 4 new tests in `tests/test_backup_restore.py` cover the redact
  helper, the redacted-default round-trip, env allowlist, and source-
  kind allowlist.

### Changed
- **Doc clarity pass** based on a fan-out audit:
  - Purged stale references to `findajob` / Find a Job from README,
    CONTRIBUTING, CLAUDE.md, MAINTENANCE.md. Source count now reads
    "17" everywhere (was "18" in three places after v0.9.1's removal).
  - Hedged stale figures (`24,000+ jobs`, `69 unit tests`) into
    `thousands of jobs` / `100+ unit tests` — exact numbers go stale
    every release.
  - MAINTENANCE.md picked up an explanatory note that `findajob` was
    removed in v0.9.1 with a pointer to audit log §10.
  - TASKS.md catches up to v0.10.3 → v0.11.1 (the WAL-checkpoint item
    was shipped in v0.10.3 but still listed as open).

## [0.11.1] — 2026-05-28

### Fixed
- Stop tracking `data/jobhunt.log`. Same class of bug as v0.10.4: a
  new runtime file (the rotating log added in v0.11.0) wasn't in
  `.gitignore` and got committed once. Cleanup commit; no behaviour
  change.

## [0.11.0] — 2026-05-28

### Added
- **`jobhunt backup` / `jobhunt restore` commands.** Round-tripping
  zip backup of the things you'd actually care about losing — saved
  searches, CV profile, alerts, local source overrides, environment
  settings. Skips the transient job database (gets re-scraped).
  Schema-versioned (schema=1), so future releases can migrate older
  backups without losing data. 6 new tests cover the round-trip,
  malformed zips, missing payload, wrong schema, and missing files.
- **File-based logging at `data_dir/jobhunt.log`.** Rotating handler
  (1 MB × 3 backups = ~4 MB max disk use). When a user hits a bug
  they can attach this file to a GitHub issue. Falls back silently
  to stderr-only on read-only filesystems.
- **`db.check_integrity()`** — wraps SQLite's `PRAGMA integrity_check`,
  returns `(ok, message)`. Available for `jobhunt doctor` to surface
  silent DB corruption before it bites.

### Why this matters for long-term operation
The three additions above together close the "what if something goes
wrong years from now" loop:
- Backup protects against an accidental Clear-all-jobs click + against
  DB corruption + against moving to a new machine.
- File logging gives the user real evidence to attach when reporting
  a bug, without having to know what stderr is.
- Integrity check lets `jobhunt doctor` flag a quietly-corrupt DB
  before it becomes a data-loss event.

## [0.10.4] — 2026-05-28

### Fixed
- Stop tracking SQLite WAL sidecar files. v0.10.3 turned on WAL mode
  but didn't update `.gitignore`, so `data/jobhunt.db-wal` and
  `data/jobhunt.db-shm` got committed. Also untracks
  `data/bounties.json`, which was already a per-machine cache file
  but had been tracked since an earlier commit. No code-behaviour
  change beyond the cleanup.

## [0.10.3] — 2026-05-28

### Fixed
- **CV upload no longer returns 500 on bad files.** Empty PDFs/DOCX/TXT,
  files renamed to a supported extension but with mismatched content,
  and image-only PDFs all now return a clear 400 with a user-friendly
  message instead of bubbling pypdf/python-docx exceptions. 8 new
  tests in `tests/test_cv.py` lock down each failure mode.
- **`/alerts/create` truncates over-long inputs.** Previously a
  5000-character name was being saved verbatim despite the
  `String(128)` column declaration. Now: name capped at 128, free-text
  fields at 256, tag lists at 50 entries. 3 new tests in
  `tests/test_robustness.py`.

### Added
- **`PRAGMA wal_checkpoint(PASSIVE)` after every refresh.** Keeps the
  SQLite `-wal` sidecar file from growing unbounded on long-running
  installs. PASSIVE mode never blocks readers and skips quietly when
  another connection is mid-transaction.
- **Keyboard shortcuts.** `/` focuses the keyword search, `r` triggers
  Refresh, `?` opens `/help`. Skipped while typing in any input so we
  never hijack characters.
- **HTMX loading skeleton.** A subtle shimmer + dimmed cards appear
  while `/jobs` requests are in flight, so filter changes don't feel
  laggy. Pure CSS + a class toggle, no extra JS work per request.

## [0.10.2] — 2026-05-28

### Added
- **Germany non-tech parity** — 9 new Arbeitsagentur entries mirroring
  the UK Reed catalogue (Reinigungskraft, Lagerarbeiter, Verkäufer
  Einzelhandel, Küchenhilfe, Lieferfahrer, Empfangskraft, Kundenservice,
  Pflegehelfer, Sicherheitsmitarbeiter). German users now get the same
  zero-experience local-jobs experience the UK has had since v0.9.1.
  No API key required.

## [0.10.1] — 2026-05-28

### Fixed
- **SQLite "database is locked" errors under concurrent writes.** The
  category-backfill background thread + an incoming request could
  contend on the same SQLite file. Now: WAL journal mode (readers go
  through while one writer works), `synchronous=NORMAL` (safe with WAL,
  noticeably faster commits), 30s busy-timeout (writers wait quietly
  instead of erroring). `check_same_thread=False` on the connection so
  the backfill thread can share the engine. End-to-end: 5/5 stress-runs
  of the full test suite green where 2/5 had been flaky before.
- Hardened the auto-disable test fixture: autouse cleanup before AND
  after each test so a previous failure leaving rows can't pollute the
  next run.

## [0.10.0] — 2026-05-28

### Added
- **FTS5 full-text search.** Keyword queries (`?q=`) now use SQLite's
  FTS5 inverted index instead of a triple `LIKE %x%` scan — typically
  10–100× faster at the 24k+ row scale jobhunt operates at. The index
  is auto-created on startup, kept in sync via INSERT / UPDATE / DELETE
  triggers, and falls back to LIKE on SQLite builds that lack FTS5.
  User input is sanitised (FTS5 operators stripped, each term quoted as
  a phrase) so neither garbage nor injection attempts can 5xx the API.
- **`POST /api/settings/test-keys`** — live validation for Jooble +
  Reed API keys with instant ✓/✗ feedback. The Settings page now has a
  "Test keys" button next to Save; users no longer find out at the
  next scrape that a key is invalid.
- **In-app help page at `/help`.** Plain-English FAQ covering every
  filter, the salary-estimate badge, the Local Jobs non-tech default,
  API key setup, update + uninstall flows, troubleshooting common
  errors, and the privacy posture. Linked from the main nav.
- **Skip-link + ARIA labels** — minimum-viable accessibility pass on
  the Help page and the global Refresh button.
- **Richer `/api/healthz`** — now returns job count, source-health
  summary, last refresh timestamp, and DB size on disk. A single
  request gives the full operational picture for monitoring scripts.

### Changed
- `_disabled_sources` now uses a `ROW_NUMBER()` window function to fetch
  the latest N rows per (source, board), so the auto-disable decision
  no longer depends on the global size of the scrape_runs table.

## [0.9.2] — 2026-05-28

### Added
- **Auto-disable broken sources.** After three consecutive scrape
  failures (HTTP error or zero jobs returned), a source is silently
  skipped on the next refresh until something changes — preventing
  wasted requests on dead URLs and reducing log noise. A single
  successful scrape re-enables the source automatically. Defensive
  counterpart to the `source-maintenance` skill's research role.
- **Source health badge on the Settings page.** Shows "X offline · Y
  returning no jobs of N checked", with a link to the per-source detail
  page. Lets the owner spot decay before users do.
- **`GET /api/sources/health`** — JSON summary `{offline, attention,
  total}` for scripted consumption.

### Changed
- `scrape_all()` return value now includes a `skipped` count.

## [0.9.1] — 2026-05-28

### Fixed
- **Removed the Find a Job (DWP) scraper.** The DWP deprecated the
  `?format=rss` query parameter and every URL now returns HTML; the
  scraper was silently returning 0 jobs across all 19 default entries
  shipped in v0.9.0. Caught by the new source-maintenance skill on its
  first run. UK non-tech coverage is now via Reed broader keywords
  (cleaning, warehouse, retail, kitchen, delivery, reception, customer
  service, care, security) which is more reliable but does require the
  free Reed API key entered on the Settings page.
- **Arbeitnow scraper is now resilient to pagination rate-limits.** It
  was raising on 403/429 mid-walk and killing the nightly refresh;
  treats it as end-of-feed instead.

### Added
- **`docs/MAINTENANCE.md`** — durable maintenance handbook covering
  source failure modes, repair decision tree, free-API trust hierarchy,
  per-country coverage map, and the chronological audit log.
- **`.claude/skills/source-maintenance/SKILL.md`** — a paired AI
  skill that runs the maintenance workflow end-to-end on demand.
- **`jobhunt doctor --json`** — machine-readable health output for
  scripted maintenance.

## [0.9.0] — 2026-05-28

### Added
- **CV upload always works.** Without `sentence-transformers` installed, jobhunt now
  falls back to a keyword-overlap CV match (skills + languages) so uploads no
  longer return `{"detail": "CV matching requires sentence-transformers..."}`.
  Installing the `[match]` extras transparently upgrades to semantic cosine
  similarity. No more terminal commands to "make it work".
- **One-click uninstall.** The Settings page now has an actual **Uninstall jobhunt**
  button — it runs `uv tool uninstall jobhunt-app` / `pipx uninstall …` and shuts
  the server down so the OS releases the files. No more copy-pasting commands.
- **Split Check vs Install for updates.** The old single button mixed
  "check for updates" with "install the upgrade now", and the failure messages
  were opaque. *Check for updates* is now passive (calls `/api/check-update`)
  and surfaces a separate **Install update** button only when a new version is
  available.
- **Local Jobs pivot: zero-experience first.** The `/local` page is now built
  around the everyday entry-level work most people actually need near home —
  cleaning, retail, warehouse, hospitality, care, customer service, driving,
  reception, security. Tech / software is still one click away via the new
  *What kind of work* dropdown.
- **Find a Job (DWP) scraper.** Free UK government job board with strong
  non-tech coverage. 19 default sources cover all major UK cities plus
  category-targeted pulls (cleaning, warehouse, retail, kitchen, delivery,
  reception, customer service, care, security).
- **Tech / non-tech classifier.** Every job is now tagged with a `category`
  (`tech`, `nontech`, or `other`) at scrape time; a one-time migration
  back-classifies existing rows on first boot.
- **Bug bounty reward data — actual numbers, never estimates.** Intigriti,
  YesWeHack, and Bugcrowd payout ranges are now pulled directly from the
  upstream data. HackerOne entries surface `offers_bounties` / `offers_swag`
  plus response-efficiency % and average days-to-resolve. New filters: *Pays
  cash* / *Cash or swag*, plus sort by highest max payout, highest min
  payout, or most responsive.
- **Cache-busted static assets.** `style.css?v={{ version }}` and
  `app.js?v={{ version }}` on every template so browsers stop serving stale
  copies after upgrade.

### Changed
- **Career stage filter no longer duplicates "Internship".** The Jobs page used
  to show "intern" in *Level* AND "Internship" in *Job type*. Career stage is
  now permanent-role seniority only (entry → senior); use *Job type →
  Internship* for the contract type. Adds an explicit hint on both filters.
- **/sources page no longer 500s after an in-place upgrade.** Wrapped the
  YAML loader in a graceful fallback that serves an empty state with an
  inline retry hint instead of crashing the page.
- **CV match modes are visible.** The CV page shows whether you're in
  semantic or keyword mode and how to upgrade if you want the bigger model.

### Fixed
- After clicking the old *Check for updates* button (which actually ran the
  install), subsequent `/sources` and `/api/refresh` requests could 500.
  Splitting check from install + hardening the sources renderer closes both
  symptoms.

## [0.7.2] — 2026-05-28

### Added
- **4 app sections**: Jobs (main search), Local Jobs (UK/Germany entry-level),
  Freelance & Contract, Bug Bounty (HackerOne/Bugcrowd/Intigriti/YesWeHack).
- **Local Jobs page**: 35+ UK/Germany regions (Whitechapel, Stuttgart, Berlin,
  Manchester, etc.). Max-experience filter (0-5 years). 200 results per search.
- **Freelance page**: filters Contract/Freelance jobs with keyword, work mode,
  salary. Sorted by most recently posted.
- **Bug Bounty page**: 871 programs from bounty-targets-data (GitHub). Search
  by company/domain, filter by platform. Auto-refreshes with main refresh.
- **Settings page**: API key fields (Jooble + Reed), user location, check for
  updates button, clear all jobs button, uninstall instructions.
- **Desktop shortcut**: Windows install script creates `jobhunt.bat` on Desktop.
- **Intern-focused sources**: SimplifyJobs internships/new-grad, German
  Praktikum/Werkstudent/Ausbildung/Junior/Trainee, Reed UK junior/graduate.
- **15 UK company boards**: Trustpilot, Wise, Checkout.com, Starling Bank,
  Snyk, Onfido, iwoca, Airwallex, 1Password, Made Tech, Hugging Face, etc.
- **PyPI publishing**: `pip install jobhunt-app` works. Published via uv.

### Changed
- **UI overhaul**: newspaper theme replaced with clean modern blue/white design.
  Dark mode. Mobile responsive. Rounded cards, pill badges.
- **Filters simplified**: Job type, Degree, Visa now clean dropdowns (4 fixed
  options) instead of dynamic radio buttons that showed 30+ raw values.
- **Employment type normalization**: 60+ raw variants (FullTime, berufserfahren,
  Working student, etc.) mapped to 4 canonical types (Full-time, Part-time,
  Contract, Internship). DB migration runs on every startup.
- **Level detection overhauled**: split into title-only and description-only
  patterns. Now catches co-op, ausbildung, azubi, trainee, apprentice,
  associate, "0-1 years". False positives fixed (e.g. "graduate degree" no
  longer triggers entry-level on senior roles).
- **Apply link**: shows "Apply" instead of truncated URL.
- **All JS moved to app.js**: no inline scripts. Fully CSP compliant.
- **Install scripts**: uninstall old versions before installing, create desktop
  shortcut, show version after install.

### Fixed
- CSP blocked inline scripts in settings.html — buttons were dead.
- PowerShell installer crashed: `$ErrorActionPreference='Stop'` treated uv
  stderr as fatal error.
- Old CSS variables (`--moss`, `--font-display`) left in templates after rewrite.
- Missing root `.muted` CSS class — dozens of elements unstyled.
- Dark mode: hardcoded `rgba(0,0,0,0.1)` borders invisible.
- `clear-data` deleted SQLite file breaking engine pool — now truncates tables.
- `jobhunt update` CLI used wrong package name (`jobhunt` instead of `jobhunt-app`).
- `/api/uninstall` returned `jobhunt` instead of `jobhunt-app`.
- Salary parsing: "1.5k" was parsed as 15,000 (dot removed before k-handler).
- Windows notifications: quotes in job titles broke PowerShell command.
- "Senior Associate Engineer" false-positive as entry-level — added negative lookbehind.
- 12+ broken source slugs removed (companies changed ATS platforms).

### Data
- 24,303 jobs from 130+ sources across 17 scrapers.
- 3,329 intern/entry/junior roles detected (13.7%).
- 871 bug bounty programs cached.
- 1,040 London jobs, 1,056 Stuttgart jobs, 2,334 remote jobs.

### Tested
- 69 unit tests, 7 E2E Playwright tests, 25 endpoint checks, 20 edge cases.
- 3 full iteration passes with 6 parallel audit agents.

## [0.1.0] — 2026-05-22

### Added
- Initial release with 9 ATS adapters, editorial UI, CV matching, saved
  searches, desktop alerts, Docker support, CSRF defence, CSP headers.
- 11,388 jobs from 38 sources. 53 tests passing.
