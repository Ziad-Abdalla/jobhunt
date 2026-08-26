# Changelog

## [Unreleased] — expansion 2026-07

### Added (2026-08-05 — full-auto approve, owner override)
- **Server-side auto-approve** (`JOBHUNT_AUTO_APPROVE`, default OFF): a
  non-error draft is approved the moment the actuator posts it, and the
  actuator's derived answers to unmapped form questions join the answer
  bank automatically (secret-like values refused). Reverses the earlier
  universal-approve-tap posture on the owner's explicit 2026-08-05
  instruction. Two brakes remain: drafts containing a blank unmapped
  question park for the human (never submit a blank answer), and
  `JOBHUNT_AUTO_APPROVE_DAILY_CAP` (default 15) parks everything beyond
  the cap. The actuator playbook gains the paired derivation rules:
  answers must be grounded in the owner's CV/profile/answer bank, never
  invented; ungroundable legal/background/compensation questions stay
  blank so the draft parks.

### Fixed (2026-08-05 — final walkthrough session)
- **Summary keyword casing:** CV-matched JD keywords reached the generated
  summary lowercase ("ai, ci-cd, javascript"); acronyms and proper nouns now
  render properly cased ("AI, CI/CD, JavaScript") via a display map in
  `cv_docx.py`. Attested skills keep their owner-entered casing; unknown
  generic vocabulary still passes through unchanged.

### Added (2026-07-25 — attested-skills CV auto-tailoring)
- **Tailor-sheet attest forms:** the `/apply/tailor/<job>` sheet gains a form
  where the applicant attests which suggested skills are genuinely theirs and
  where they were used (project or role placement); attested skills are
  stored per profile (`AttestedSkill`, in `cowork_models.py`, PII-side).
- **Per-job tailored CV in every Cowork export:** `cv_attachment` in the
  export now includes `tailored` (bool). When true, jobhunt has generated a
  per-job docx at `data_dir/tailored_cvs/<app_id>/<Name>_CV_<Company>.docx`
  by reordering and lightly augmenting sections from the applicant's base
  docx with attested, JD-relevant skills; when false, `path` is the base CV
  PDF and `reason` explains why (no docx master configured, or generation
  failed).
- **Calibration + drift guard:** before first use, and whenever the base
  docx changes (content hash check), jobhunt calibrates the master docx
  (locates the summary and skills/stack paragraphs it will edit) and refuses
  to auto-tailor if calibration cannot find the expected structure, falling
  back to the base PDF instead of silently mangling the file.
- **New dependency:** `python-docx`, used only by the new `cv_docx.py`
  module (applicant-side; the scrape pipeline is structurally guarded from
  importing it, same as `cowork_models`).

### Added (2026-07-22 — full-auto apply, pieces A–F)
- **CV auto-selection (A):** the profile stores two CV paths (Egypt /
  remote variants); every Cowork export picks one per job
  (location-first rule, Wuzzuf always Egypt, unresolved → remote) as
  `cv_attachment: {path, variant, reason}`.
- **Auto-queue (B, default OFF — `JOBHUNT_AUTO_QUEUE=1`):** after each
  scheduled refresh, jobs matching any saved search are queued
  best-relevance-first, skipping already-applied jobs, companies applied
  to within 14 days (`JOBHUNT_AUTO_QUEUE_COMPANY_COOLDOWN_DAYS`), and
  category mismatches. Auto rows are badged in the queue and
  bulk-rejectable; an optional daily cap exists
  (`JOBHUNT_AUTO_QUEUE_DAILY_CAP`, 0 = unlimited).
- **Draft annotations (C):** every draft is server-annotated
  (clean-mapping check, sensitive-field chips — salary/visa/EEO/cover
  letter/essay heuristic — agent-note tripwire, open questions) so the
  universal approve tap is a 3-second glance. The state machine and both
  human gates are unchanged.
- **Standard answers + answer bank (C2):** profile gains notice period,
  earliest start, "how heard" and EEO defaults (exported in the field
  mapping) plus derived per-job `authorized_to_work` /
  `needs_sponsorship` answers; unanswered draft questions are asked once
  at the approve gate, saved to a learning answer bank (editable on
  /profile), and included in every later export.
- **Outcome layer (D):** submitted applications track
  awaiting_reply/replied/interview/offer/rejected_by_employer/no_response
  via the queue UI or `POST /api/cowork/outcome` (inbox monitoring);
  every change pings the channels.
- **Discord channel (E):** `JOBHUNT_DISCORD_WEBHOOK_URL` (masked on
  Settings, backup-redacted) joins desktop/Telegram/email in the alert
  fan-out.
- **Actuator playbook (F):** the operator-side playbook and its setup
  script are maintained privately. The contract every actuator must honour
  is documented in `docs/cowork-handoff.md`.

### Fixed (2026-07-22 — test suite mutated the developer's real data)
- **The unit suite ran against the real data dir.** `tests/conftest.py` now
  redirects `JOBHUNT_DB_PATH` + `JOBHUNT_LOCAL_SOURCES_FILE` to a per-run
  temp dir before any jobhunt import. Without it, `test_backup_restore`'s
  real `jobhunt backup` → `restore` round-trip rewrote the live `.env` —
  restore keeps only its env allowlist, so the JSearch/Careerjet keys and
  scheduler settings silently vanished (previously misdiagnosed as the
  installed app's Settings save) — and `_clear_searches()` deleted the
  user's live saved searches. Pinned by `tests/test_isolation.py`; the
  Playwright e2e suite now seeds its own fixture jobs instead of leaning
  on the developer's scraped DB.

### Fixed (2026-07-22 — Careerjet live probe)
- **Careerjet now sends a `Referer` header.** The live API rejects
  referer-less calls with 403 "Undeclared referrer" — a requirement absent
  from the offline docs the adapter was built against. Live-verified with a
  real affiliate ID: 100 Egypt jobs (Capgemini, Deloitte, ZainCash…) across
  two `en_EG` boards.

### Added (2026-07-21 — AI-role targeting + new sources)
- **AI/LLM employer boards** (all live-probed): Hugging Face, Together AI,
  xAI, LangChain, DeepL, Character AI, Pinecone, Aleph Alpha, Stability AI,
  Glean, Fireworks AI, Writer, Harvey, Sierra, Poolside — plus Thndr
  (Egypt fintech) and, via board discovery, Scout24, Intuition Machines
  (hCaptcha), Bayut|dubizzle (MENA), B12, EMARKETER, Seesaw, BDG Media,
  Great Minds. sources.yaml is now 204 entries.
- **AI/ML role searches**: machine-learning/AI keyword boards for Jooble
  (Egypt/UK/Germany), Reed, and Arbeitsagentur, so applied-AI roles stop
  falling through the generic "developer" nets.
- **Reddit adapter** (`reddit`): [Hiring]-marked posts from subreddit
  hiring threads (r/forhire, r/jobbit, r/RemoteJobs) via the old.reddit
  Atom feed — the freelance/gig lane. Requests serialized ~30s apart with
  a 429 retry (Reddit rate-limits unauthenticated clients hard).
- **Careerjet adapter** (`careerjet`): BYO affiliate ID (free partner
  account), off by default. Real Egypt index (locale `en_EG`) plus 90
  other locales; `<keywords>|<location>` search boards like Jooble/JSearch.
  Settings-page field (masked, backup-redacted).
- **Workable v1 fallback**: some accounts (Hugging Face, Intuition
  Machines, Bayut|dubizzle) 404 on the v3 widget API but publish via the
  older v1 API — the adapter now falls back automatically.
- Board discovery now also harvests the `hiring-without-whiteboards`
  directory.

### Fixed (2026-07-21)
- **JSearch quota cooldown.** A full refresh now skips jsearch boards
  until `JOBHUNT_JSEARCH_COOLDOWN_HOURS` (default 20) have passed since
  the last pass — an unattended 6-hour scheduler was on track to burn
  ~3.6× the ~200 req/month free tier. Targeted runs
  (`only_sources={"jsearch"}`) bypass it, and the fast-poll tier refuses
  to include quota-capped sources.
- **Category backfill re-ran on every startup.** The promised
  "visited" sentinel was never implemented, so the same ~18.8k
  category='other' rows re-queued (and re-classified) on every boot —
  observed as startup churn and a "database is locked" error. One full
  pass now latches a user_version flag; later boots only visit NULL rows.
- "Full Time Contractor" (a JSearch v2 employment label) now normalizes
  to Contract instead of leaking a 5th employment type.

### Fixed (JSearch live-probe hardening)
- **Migrated to JSearch `/search-v2`** — upstream retired the `/search`
  endpoint the adapter was built against (it now 404s). v2: results under
  `data.jobs`, a proper `country` ISO param (resolved from the board's
  location, e.g. `|Egypt` → `country=eg`), `work_from_home` for remote-only,
  `language=en`, and employment type read from the stable
  `job_employment_types` enum (the singular field is localized text).
  Live-verified with a real key: 39 jobs / 34 real employers across the 4
  Egypt+remote searches.
- Aggregator company labels added via the Sources page are auto-wrapped in
  parentheses for `jsearch`, so the label can never override the real
  employer names on scraped jobs.
- Level extraction: "Fresher" titles (MENA/India English for entry-level)
  now classify as `entry` instead of falling through to a description match.
- The Sources page now accepts `jsearch` search boards (`<query>|<location>`
  with spaces) — the board-slug validation predated the adapter and rejected
  them; other sources keep the strict ATS-slug rule.
- JSearch requests are serialized with ~1.5s spacing and one retry on 429:
  the free tier rate-limits per second, and concurrently-scraped boards were
  all failing with 429 (observed on the first live run).
- Settings saves write the `.env` atomically (temp file + rename). A save
  landing while another was mid-write could read the file as empty and
  rewrite it without the stored API keys.
- **Saved settings now survive restarts.** The Settings page saves keys +
  location to `data_dir/.env`, but nothing ever read that file back on
  startup — every saved API key and the user location silently reverted on
  restart (long-standing; also why `jobhunt doctor` never saw UI-saved
  keys). Settings construction now includes the user file, with real
  environment variables still taking priority.

### Added (P8 — indirect Egypt/MENA + remote via JSearch)
- **JSearch (RapidAPI) adapter** — a bring-your-own-key, off-by-default
  source that reaches Egypt/MENA + remote jobs jobhunt can't scrape
  directly (Google-for-Jobs aggregation over Wuzzuf/Bayt/LinkedIn/company
  postings). Paste a free RapidAPI key on the Settings page, then add a few
  targeted `jsearch` searches (e.g. `developer|Egypt`, `developer|remote`).
  Free-tier-aware (capped, low-frequency). Key is masked + redacted from
  backups like the other keys.

### Added (P9 + P10 — CV tailoring + ATS readiness)
- **Per-job tailoring sheet** (`/apply/tailor/<job>`, download as `.md`, or
  `jobhunt tailor <job>`). Shows which of a job's keywords your CV already
  covers and which are missing, a suggested Skills line that leads with the
  matched keywords (ATS keyword priority), and a fill-in summary scaffold.
  Deterministic keyword matching — no AI, and it never invents a skill or
  achievement. Works for non-tech + Egypt/blue-collar roles too (generic
  role vocabulary, not just software).
- **ATS-readiness linter.** Flags the things that make applicant-tracking
  systems mis-parse a resume: missing contact info, missing standard
  section headers, multi-column/table layouts, garbled encoding, and
  unreasonable length.
- The Cowork export carries a per-application `tailoring` block (coverage +
  matched/missing keywords) so the handoff includes keyword guidance.

### Added (P7 — off-machine alerts + coverage growth)
- **Telegram + email alerts.** Saved-search alerts now fan out to Telegram
  (set `JOBHUNT_TELEGRAM_BOT_TOKEN` + `JOBHUNT_TELEGRAM_CHAT_ID`) and email
  (`JOBHUNT_SMTP_HOST` + `JOBHUNT_SMTP_TO`, STARTTLS) on top of the desktop
  notification — so you catch a new match while away from the machine. Each
  channel self-gates on its config; with nothing set, behavior is exactly
  the old desktop-only. Tokens/passwords are redacted from `jobhunt backup`.
- **Per-search source filter + priority fast-poll.** A saved search can
  target only chosen sources, and a "priority" search gets a fast-poll tier
  (`JOBHUNT_FAST_POLL_MINUTES`) that re-scrapes just its sources on a tight
  interval — an early-application edge without hammering all 150+ sources.
- **`jobhunt discover-boards`.** Harvests new ATS board slugs from public
  GitHub company directories and writes UNVERIFIED candidates to a review
  file (never straight into `sources.yaml` — run `jobhunt doctor` first).
- **2 MENA employer boards** (Tamara, Careem via Greenhouse — live-verified),
  widening Egypt/GCC coverage.

### Added (P6 — applicant profile + Cowork application handoff)
- **Applicant profile (`/profile`).** The details application forms ask for,
  entered once. Local-only by construction: the page and every handoff
  endpoint answer loopback requests only (even with `JOBHUNT_HOST=0.0.0.0`),
  the schema has no passport/national-ID fields, and saving refuses
  key-like text (AWS/`sk-`/`ghp_`/PEM/JWT patterns) so credentials can
  never land in the store.
- **Application queue with two human gates.** Queue a job on /apply
  (gate 1); when an assistant drafts it, the exact fields it would fill
  are shown for review, and nothing submits without your Approve (gate 2)
  — enforced server-side: a submission receipt for an unapproved
  application is refused.
- **Local handoff API for assistants** (`/api/cowork/export`, `/draft`,
  `/receipt` + `jobhunt apply export`), default-OFF behind
  `JOBHUNT_COWORK_EXPORT=1` and loopback-only. Job descriptions are
  exported wrapped as `__untrusted_data__` (never instructions), field
  values come only from a fixed jobhunt-generated mapping, and each
  application carries a hard-stop domain allow-list. Contract:
  `docs/cowork-handoff.md`. jobhunt holds zero Gmail/OAuth credentials.

### Added (P5 — apply-target classification + /apply page)
- **Every job's apply link is classified** by what sits behind it:
  `ats` (a hosted form on a known ATS — Greenhouse, Lever, Ashby, Workable,
  Workday, …), `aggregator_relay` (applying goes through a job board —
  either on the board itself, like Wuzzuf, or one hop to the real form), or
  `company_site` (an arbitrary web form on the company's own site). Pure
  URL-host classification against curated allow-lists — no guessing, and
  hostile-URL hardening (WHATWG backslash normalization, strict DNS host
  gate) so a crafted link can't earn a false "ATS" label. New
  `apply_kind`/`apply_domain` fields, backfilled in the background on first
  boot after upgrade.
- **New /apply page.** "Where does applying actually happen?" — filter the
  ranked job list by application flow (green ATS form / amber job board /
  red own-site badges, with live counts per bucket). Groundwork for the
  Cowork application handoff (P6); `AUTO_SUBMIT_DOMAINS` marks the
  Greenhouse/Lever-class subset that assisted apply may ever target.
- `/api/jobs` now returns `apply_kind` and `apply_domain`.

### Fixed (P5)
- **`ix_jobs_geo_restrict` now exists on upgraded databases.** The P3
  migration added the column but never the index (SQLite `ALTER` doesn't
  create model indexes); geo-filtered queries on upgraded installs were
  full-scanning.

### Added (P4 — ranking reflects reachability)
- **Relevance sort blends CV match.** Once a CV is uploaded, the default
  "relevance" sort ranks by `score × (1 + 1.5·cv_match)` — no more manually
  switching to the CV sort and losing recency. The stored match % is unchanged.
- **Unreachable remote jobs sink.** When `JOBHUNT_USER_LOCATION` is set,
  jobs geo-restricted to a region you're not in (e.g. "US only" seen from
  Cairo) are demoted (×0.35) in relevance and CV sorts — demoted, never
  hidden, and `unknown`/`restricted-other` buckets are never penalized.
  The region resolves only from a *recognized* country name (English or
  native spelling, EEA counts as EU); unrecognized locations like
  "New York, NY" never penalize anything. Cards show the eligibility badge
  and the sidebar discloses when demotion is active.

### Added (P3 — Egypt/Arabic extraction quality)
- **Arabic-aware extraction.** Level, employment type, remote/hybrid/onsite,
  and years-of-experience keyword tables now cover Arabic (Wuzzuf postings);
  Arabic-Indic digits are normalized before numeric extraction. Arabic
  postings with no signal stay `unknown` instead of being guessed
  mid/Full-time — they now appear correctly in junior/intern filters.
- **Wuzzuf structured metadata.** `career_level` / `experience` / `job_type`
  now map directly to level, min-years, and employment type
  (structured-fields-first, regex as fallback).
- **Remote eligibility filter.** New `geo_restrict` field
  (us-only / uk-only / eu-only / restricted-other / unrestricted / unknown)
  extracted from every JD, filterable on the Jobs page — "Remote (US only)"
  no longer looks apply-able from Egypt.
- **Egypt/GCC salary estimates.** Estimator gains egypt (EGP) and gcc (AED)
  regions; Cairo jobs no longer priced as generic-USD "other".
- **/local knows Egypt.** Cairo/Giza/Alexandria (+ Arabic aliases) region
  expansions; job cards render Arabic titles RTL via `dir="auto"`.

### Fixed (P3)
- **Arabic titles no longer break dedup.** Fingerprint normalization is
  Unicode-aware + NFC (previously an all-Arabic title normalized to an empty
  string); a one-time migration rewrites affected stored fingerprints
  (gated on `PRAGMA user_version`).

### Added
- **5 new free, no-auth sources.** `wuzzuf` (largest Egypt job board — closes the
  project's zero-Egypt-coverage gap, ~2900 live jobs via RSS), plus worldwide-remote
  `remotive`, `workingnomads`, `weworkremotely` (per-category), and `pythonjobs`
  (python.org). 22 adapter types now ship (was 17). One respx test each; all
  live-verified returning real jobs.

### Fixed
- **Three silent job-losing pipeline bugs.** (1) Fingerprint collisions overwrote
  distinct openings' apply URLs — same-source distinct reqs now stay separate rows
  while cross-source duplicates still merge. (2) Remote-synonym dedup split one remote
  job into several rows — "Remote"/"Worldwide"/"Anywhere"/"100% Remote" now canonicalize
  to `remote` (region-qualified remotes stay distinct). (3) Auto-disabled sources never
  self-healed — they're now re-attempted every `disabled_retry_hours` (default 24h) so a
  transient outage recovers instead of killing a source forever.
- **`jobhunt doctor` concurrency cap.** Now bounded by `settings.concurrency` (new
  `gather_bounded` helper) instead of firing all 150+ sources at once — avoids 429/WAF
  blocks during the maintenance skill's post-add health check.

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
