# CLAUDE.md — jobhunt project context

## What this is
Local-first Python job aggregator. FastAPI + Jinja2 + HTMX + SQLite. No build step.
PyPI: `jobhunt-app`. CLI: `jobhunt`. MIT licensed, public repo.

## 4 Sections
- **Jobs** (`/`) — main search, 15 filters, 24k+ jobs from 130+ sources (tech-focused).
- **Local Jobs** (`/local`) — **zero-experience local roles (cleaning, retail,
  warehouse, hospitality, care, customer service, driving)** with a *What kind of
  work* toggle for tech. UK + Germany focus. Defaults to `category=nontech`.
- **Freelance** (`/freelance`) — contract/freelance roles
- **Bug Bounty** (`/bounties`) — 870+ programs from HackerOne/Bugcrowd/Intigriti/YesWeHack.
  Reward ranges come directly from upstream (Intigriti, YesWeHack, Bugcrowd); we
  never estimate. HackerOne entries expose response-efficiency % and pays-cash flag.

## Session continuity
Resume anchor: [`docs/internal/SESSION_LOG.md`](docs/internal/SESSION_LOG.md) — read the latest entry
first. Owner-side action checklist for each session lives in `docs/sessions/`.
A session **must** end by appending a SESSION_LOG entry (see `docs/internal/SESSION_LOG.md` for the template).

## Long-term maintenance
External sources rot — APIs expire, ATS slugs change, free tiers tighten.
Two paired artefacts keep the data layer healthy:

- **`docs/MAINTENANCE.md`** — the rulebook. Source taxonomy, failure
  modes, repair decision tree, free-API trust hierarchy, chronological
  audit log. Read first when investigating "why no jobs in country X?"
  or before adding a new source.
- **`.claude/skills/source-maintenance/SKILL.md`** — paired AI workflow
  that runs the rulebook end-to-end. Triggers on phrases like "check our
  sources", "what's broken", "find new APIs", "source maintenance". On
  each run it: detects broken sources via `jobhunt doctor --json`,
  diagnoses via the decision tree, researches replacements, applies +
  verifies the changes, appends to the audit log.

The skill is Claude-Code-specific; the rulebook is plain markdown so any
AI agent (or human contributor) can follow it. Both ship with the repo.

## Key rules
- **No inline `<script>` tags** — CSP is `script-src 'self'`. All JS in `static/app.js`.
- **Filters must be fixed dropdowns**, not dynamic radio buttons from DB facets.
  Dynamic values showed 30+ unnormalized employment types — never again.
- **Employment types** normalize to exactly 4: Full-time, Part-time, Contract, Internship.
  Map lives in `refresh.py` `_EMPLOYMENT_TYPE_MAP` (60+ entries). DB migration on startup.
- **Career stage vs Job type don't both say "Internship".** Career stage = permanent-role
  seniority (entry → senior); Job type → Internship is the contract type. The Jobs page
  hides level=intern radio for this reason — hint text is required on both filters.
- **Bug bounty rewards: real numbers only.** Never estimate min/max; if upstream
  data is silent, the field stays None and the UI omits it. User explicitly
  set "extreme accuracy" as the gate.
- **CV match never blocks on missing ML deps.** `cv.py` falls back to keyword
  scoring when sentence-transformers isn't installed. The upload always works;
  the bigger model is an opt-in extras install.
- **Level detection** is title-first, description-second (`extract.py`). Watch for false
  positives: "graduate degree" != "graduate role". Senior > entry priority in title.
- **PyPI package name** is `jobhunt-app` (not `jobhunt` which was taken by someone else).
- **When adding sources**: run `jobhunt doctor` to verify. Remove 404s promptly.
- **Templates**: include `?v={{ version }}` on `style.css` and `app.js` (Jinja
  global set in `main.py`). Without this, browsers serve stale CSS after upgrades.
- **Keep README, CONTRIBUTING, CHANGELOG, CLAUDE.md up to date** with every feature change.

## Testing
```bash
pytest -q                    # 102 unit tests (was 69 before v0.9.0)
pytest -m e2e                # 11 Playwright E2E tests
ruff check src/              # style + bug lint
```

## Architecture
- `main.py` — all routes (8 pages + ~16 API endpoints incl. /api/uninstall-now)
- `scrapers/` — 18 ATS adapters (including `findajob` for UK DWP free non-tech data)
- `sources.yaml` — 130+ company boards + Find a Job non-tech entries
- `refresh.py` — scrape pipeline + employment type normalization + category derivation
- `extract.py` — regex extractors (level, remote, salary, skills, languages,
  **`classify_category`** → tech/nontech/other)
- `bounties.py` — per-platform parsers (`_parse_hackerone`/`_parse_bugcrowd`/
  `_parse_intigriti`/`_parse_yeswehack`); BountyProgram now carries
  `min_bounty`, `max_bounty`, `currency`, `pays`, `state`,
  `response_efficiency_pct`, `avg_days_to_resolve`.
- `filters.py` — search query builder, 15 stackable filters
- `cv.py` — `has_semantic_model()`, `keyword_score()`, `embed_text()` (optional)
- `config.py` — pydantic-settings, reads from env vars + `.env` file
- `db.py` — SQLAlchemy + SQLite, forward-only column migrations + employment type
  normalization + **`_backfill_categories`** (one-time pass on startup)
- `models.py` — `Job.category` column ('tech' / 'nontech' / 'other')

## Distribution
- PyPI: `pip install jobhunt-app` / `uv tool install jobhunt-app`
- Install scripts: `scripts/install.ps1` (Windows), `scripts/install.sh` (Mac/Linux)
- Windows install creates desktop shortcut (`jobhunt.bat`)
- Docker: `docker compose up`

## Known issues / watch-outs
- **uv caches aggressively** — after publishing a new PyPI version, the install
  script must use `uv cache clean` + `"jobhunt-app>=X.Y.Z"` to force the latest.
  Without this, users get stale versions and don't see new features.
- **Windows .bat shortcuts** — the desktop .bat must include the uv tool bin in
  PATH (`uv tool dir --bin`) or the `jobhunt` command isn't found.
- **Duplicate instances** — `app_mode()` checks if port 8765 is in use before
  starting. If already running, it opens the browser to the existing URL.
- **Every code change** must be published to PyPI to reach users. The install
  scripts pull from PyPI, not GitHub.
- **/sources is now wrapped in a try/except** so a missing YAML file (e.g.
  after `uv tool install --reinstall`) serves an empty state instead of 500.

## Target users
Primarily juniors and interns in software, **plus anyone looking for
zero-experience local work in the UK or Germany**. The /local page is built
around the latter use case.
