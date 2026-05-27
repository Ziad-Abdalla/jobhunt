# Contributing

Thanks for your interest in jobhunt. Contributions are welcome — the most useful
right now are **new ATS source slugs**, **bug reports**, and **new job sources
for UK/Germany entry-level roles**.

## Architecture overview

jobhunt is a local-first FastAPI app with Jinja2 templates and HTMX. No frontend
build step. Everything server-rendered.

```
src/jobhunt/
├── main.py            FastAPI routes (8 pages + API endpoints)
├── cli.py             typer CLI (jobhunt app/serve/scrape/update/doctor)
├── config.py          pydantic-settings (env vars + .env file)
├── db.py              SQLAlchemy + SQLite, forward-only migrations
├── models.py          Job, ScrapeRun, SavedSearch, CVProfile
├── filters.py         Search query builder (15 stackable filters)
├── refresh.py         Scrape pipeline + employment type normalization
├── extract.py         Regex extractors (level, remote, salary, skills)
├── scoring.py         Transparent relevance score (recency + quality)
├── salary_estimator.py Self-calibrating salary estimation
├── dedup.py           Fingerprint-based deduplication
├── bounties.py        Bug bounty program fetcher (GitHub data)
├── scrapers/          17 ATS adapters
├── templates/         Jinja2 (8 pages: index, local, freelance, bounties,
│                       alerts, cv, sources, settings)
├── static/            style.css, app.js, htmx.min.js (vendored)
└── sources.yaml       130+ default company boards
```

**4 sections in the app:**
- **Jobs** — main search with all 15 filters
- **Local Jobs** — UK/Germany entry-level by location + max experience
- **Freelance** — contract/freelance roles
- **Bug Bounty** — HackerOne/Bugcrowd/Intigriti/YesWeHack programs

## Development setup

**macOS / Linux:**
```bash
git clone <your-fork>
cd jobhunt
uv venv && source .venv/bin/activate
uv pip install -e ".[dev]"
pytest -q
jobhunt   # verify: opens http://127.0.0.1:8765
```

**Windows (PowerShell):**
```powershell
git clone <your-fork>
cd jobhunt
uv venv
.venv\Scripts\activate
uv pip install -e ".[dev]"
pytest -q
jobhunt
```

> The `[match]` extra adds CV matching (~500 MB download). Skip it unless
> you're working on that feature: `uv pip install -e ".[dev,match]"`

## Adding a new company to the default sources

1. Find the company's careers page (e.g. `https://boards.greenhouse.io/SLUG`).
2. Identify which ATS they use (URL pattern tells you).
3. Add an entry to `src/jobhunt/sources.yaml`:
   ```yaml
   - { source: greenhouse, board: <slug>, company: <Display Name> }
   ```
4. Run `jobhunt doctor` and confirm the new board shows up green.
5. Open a PR.

## Adding a new ATS adapter

Each scraper subclasses `BaseScraper` and lives in `src/jobhunt/scrapers/`.
Look at `greenhouse.py` (simple ATS) or `jobicy.py` (aggregator with salary)
for examples. You'll need:

- A public, no-auth API (or free-tier with key).
- A test in `tests/test_<source>.py` using `respx` to mock HTTP.
- Registration in `src/jobhunt/scrapers/__init__.py`.
- Use structured fields on `RawJob` when the API provides them:
  `employment_type`, `salary_min`, `salary_max`, `salary_currency`,
  `remote_structured`.

## Key conventions

- **Employment types** must normalize to: Full-time, Part-time, Contract, Internship.
  Add mappings in `refresh.py` `_EMPLOYMENT_TYPE_MAP`.
- **Level detection** is title-first, description-second (see `extract.py`
  `_TITLE_LEVEL_PATTERNS` and `_DESC_LEVEL_PATTERNS`). Be careful with false
  positives — "graduate degree" is not the same as "graduate role".
- **Filters** use fixed dropdowns, not dynamic radio buttons, to guarantee
  clean UI regardless of data quality.
- **No inline `<script>` tags** — CSP is `script-src 'self'`. All JS goes in
  `static/app.js`.
- **PyPI package name** is `jobhunt-app` (not `jobhunt`, which was taken).

## Code style

- Ruff (`ruff check src tests`).
- Type hints encouraged, not enforced.
- No comments unless they explain WHY something is non-obvious.
- Server-rendered templates only — no frontend build step.

## Testing

```bash
pytest -q          # 69 unit tests
pytest -m e2e      # 11 Playwright browser E2E tests
```

## Reporting bugs

Please include:
- Output of `jobhunt info` and `jobhunt --version`.
- Which section (Jobs / Local / Freelance / Bug Bounty).
- Which filter or action was used.
- What you expected vs what happened.
