# Contributing

Thanks for your interest in jobhunt. Contributions are welcome — the most useful
right now are **new ATS source slugs** and **bug reports against existing
sources**.

## Development setup

```bash
git clone <your-fork>
cd jobhunt
uv venv && source .venv/bin/activate
uv pip install -e ".[dev,match]"
pytest -q
```

## Adding a new company to the default sources

1. Find the company's careers page (e.g. `https://boards.greenhouse.io/SLUG`).
2. Identify which ATS they use (URL pattern tells you).
3. Add an entry to `src/jobhunt/sources.yaml`:
   ```yaml
   - { source: greenhouse, board: <slug>, company: <Display Name> }
   ```
4. Run `jobhunt scrape` and confirm the new board shows up green on `/health`.
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

Please confirm that scraping the ATS at low frequency does not violate their
ToS (`/robots.txt`, terms page) before submitting.

## Code style

- Ruff (`ruff check src tests`).
- Type hints encouraged, not enforced.
- No comments unless they explain WHY something is non-obvious.
- Server-rendered templates only — no frontend build step.

## Reporting bugs

Please include:
- Output of `jobhunt info`.
- Output of `jobhunt --version`.
- A repro: which filter / which source / what you expected vs got.
- For scraper bugs, the board slug that's failing.
