# CLAUDE.md — jobhunt project context

## What this is
Local-first Python job aggregator. FastAPI + Jinja2 + HTMX + SQLite. No build step.
PyPI: `jobhunt-app`. CLI: `jobhunt`. MIT licensed, public repo.

## 3 Sections
- **Jobs** (`/`) — main search, 16 filters, thousands of jobs from 160+ sources
  (tech-focused, plus Egypt via Wuzzuf).
- **Local Jobs** (`/local`) — **zero-experience local roles (cleaning, retail,
  warehouse, hospitality, care, customer service, driving)** with a *What kind of
  work* toggle for tech. UK + Germany focus. Defaults to `category=nontech`.
- **Freelance** (`/freelance`) — contract/freelance roles

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
pytest -q                    # 260 unit tests (was 245 before P4, 142 before P3, 102 before the 2026-07 expansion)
pytest -m e2e                # 11 Playwright E2E tests
ruff check src/              # style + bug lint
```

## Architecture
- `main.py` — all routes (7 pages + ~15 API endpoints incl. /api/uninstall-now)
- `scrapers/` — 22 adapters (findajob removed in v0.9.1; 2026-07 added wuzzuf [Egypt],
  remotive, workingnomads, weworkremotely, pythonjobs — all free/no-auth)
- `sources.yaml` — 130+ company boards + Reed/Arbeitsagentur non-tech entries
- `refresh.py` — scrape pipeline + employment type normalization + category derivation
- `extract.py` — regex extractors (level, remote, salary, skills, languages,
  **`classify_category`** → tech/nontech/other, **`extract_geo`** →
  remote-eligibility buckets, Arabic keyword tables + `is_arabic_dominant`
  don't-guess guard, Arabic-Indic digit normalization)
- `filters.py` — search query builder, 16 stackable filters + the P4 rank
  expression (relevance = `score × (1 + 1.5·cv_match) × reach_weight`)
- `scoring.py` — transparent 0–4 quality score + P4 reachability
  (`home_region_from_location`, `reachability_weights`). Stored `cv_match`
  stays pure fit — never bake geo into it; ranking applies it at query time.
- `cv.py` — `has_semantic_model()`, `keyword_score()`, `embed_text()` (optional)
- `config.py` — pydantic-settings, reads from env vars + `.env` file
- `db.py` — SQLAlchemy + SQLite, forward-only column migrations + employment type
  normalization + **`_backfill_categories`** (one-time pass on startup)
- `models.py` — `Job.category` ('tech' / 'nontech' / 'other') +
  `Job.geo_restrict` ('us-only' / 'uk-only' / 'eu-only' / 'restricted-other' /
  'unrestricted' / 'unknown')

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
