# CLAUDE.md — jobhunt project context

## What this is
Local-first Python job aggregator. FastAPI + Jinja2 + HTMX + SQLite. No build step.
PyPI: `jobhunt-app`. CLI: `jobhunt`. MIT licensed, public repo.

## 4 Sections
- **Jobs** (`/`) — main search, 15 filters, 24k+ jobs from 130+ sources
- **Local Jobs** (`/local`) — UK/Germany entry-level by location, max-experience filter
- **Freelance** (`/freelance`) — contract/freelance roles
- **Bug Bounty** (`/bounties`) — 871 programs from HackerOne/Bugcrowd/Intigriti/YesWeHack

## Key rules
- **No inline `<script>` tags** — CSP is `script-src 'self'`. All JS in `static/app.js`.
- **Filters must be fixed dropdowns**, not dynamic radio buttons from DB facets.
  Dynamic values showed 30+ unnormalized employment types — never again.
- **Employment types** normalize to exactly 4: Full-time, Part-time, Contract, Internship.
  Map lives in `refresh.py` `_EMPLOYMENT_TYPE_MAP` (60+ entries). DB migration on startup.
- **Level detection** is title-first, description-second (`extract.py`). Watch for false
  positives: "graduate degree" != "graduate role". Senior > entry priority in title.
- **PyPI package name** is `jobhunt-app` (not `jobhunt` which was taken by someone else).
- **When adding sources**: run `jobhunt doctor` to verify. Remove 404s promptly.
- **Templates**: no old CSS vars (`--moss`, `--ink`, `--rule` etc.) — use `--text-*`, `--bg-*`, `--blue`, `--green`.
- **Keep README, CONTRIBUTING, CHANGELOG up to date** with every feature change.

## Testing
```bash
pytest -q                    # 69 unit tests
pytest -m e2e                # 11 Playwright E2E tests
python3 -c "from jobhunt.main import app; from fastapi.testclient import TestClient; ..."  # endpoint checks
```

## Architecture
- `main.py` — all routes (8 pages + ~15 API endpoints)
- `scrapers/` — 17 ATS adapters, each subclasses `BaseScraper`
- `sources.yaml` — 130+ company boards (intern sources at top)
- `refresh.py` — scrape pipeline + employment type normalization
- `extract.py` — regex extractors (level, remote, salary, skills, languages)
- `bounties.py` — bug bounty fetcher from GitHub bounty-targets-data
- `filters.py` — search query builder, 15 stackable filters
- `config.py` — pydantic-settings, reads from env vars + `.env` file
- `db.py` — SQLAlchemy + SQLite, forward-only column migrations + employment type normalization on startup

## Distribution
- PyPI: `pip install jobhunt-app` / `uv tool install jobhunt-app`
- Install scripts: `scripts/install.ps1` (Windows), `scripts/install.sh` (Mac/Linux)
- Windows install creates desktop shortcut (`jobhunt.bat`)
- Docker: `docker compose up`

## Target users
Juniors and interns looking for software roles, primarily in UK and Germany.
The app should maximize quantity of entry-level listings and keep filters simple.
