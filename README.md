# jobhunt

A local-first software engineering job board aggregator with strong filtering,
optional CV semantic match, saved-search desktop alerts, a self-update
scheduler, and a polished editorial-typography UI. Free to run, runs entirely
on your machine, your data never leaves it.

## Why this exists

Most job boards either spam your inbox or hide behind anti-bot walls. This tool
pulls from **public ATS job board APIs** — the canonical source that thousands
of companies' "Careers" pages already use. Polite, stable, legal, and free.

Supported sources out of the box:

| Source           | API                                       | Notes |
|------------------|-------------------------------------------|-------|
| Greenhouse       | `boards-api.greenhouse.io`                | Best coverage |
| Lever            | `api.lever.co`                            | Strong startup coverage |
| Ashby            | `api.ashbyhq.com/posting-api`             | Modern tooling |
| Workable         | `apply.workable.com/api/v3`               | Adapter ready; add your slugs |
| SmartRecruiters  | `api.smartrecruiters.com/v1`              | Adapter ready; add your slugs |
| Recruitee        | `{tenant}.recruitee.com/api`              | Adapter ready; add your slugs |
| Workday          | `{tenant}.wdN.myworkdayjobs.com`          | Adapter ready; add your slugs |
| RemoteOK         | `remoteok.com/api`                        | Firehose of remote roles |
| Hacker News      | Algolia API for "Who is Hiring?"           | Monthly firehose |

### About LinkedIn / Indeed

There is **no free legitimate LinkedIn API**. LinkedIn killed third-party access
in 2015; their Talent Solutions API requires a paid partnership. The Python
`linkedin-api` and JobSpy's LinkedIn scraper use your account's session cookie
and risk **permanent account ban**. The same is broadly true of Indeed.

If you understand the risk and want to opt in, install the optional extra:

```bash
pip install -e ".[linkedin]"
```

…and add a LinkedIn entry to `local_sources.yaml`. This project will keep it
strictly opt-in.

## Install

Pick whichever path matches what you have. After installing, run `jobhunt app` —
that starts the server and opens it in your browser automatically.

### Option 1: Pre-built binary (no Python needed)

Download the binary for your OS from
[the latest release](https://github.com/Abdalla2004-collab/Jobhunt/releases/latest):

```bash
# Linux / macOS
curl -L -o jobhunt https://github.com/Abdalla2004-collab/Jobhunt/releases/latest/download/jobhunt-linux-x86_64
chmod +x jobhunt
./jobhunt app
```

On Windows, download `jobhunt-windows-x86_64.exe` and double-click it.

### Option 2: pipx (recommended if you have Python)

```bash
pipx install git+https://github.com/Abdalla2004-collab/Jobhunt.git
jobhunt app
```

### Option 3: From source (for development)

```bash
git clone https://github.com/Abdalla2004-collab/Jobhunt
cd jobhunt
uv venv && source .venv/bin/activate     # or:  python -m venv .venv && source .venv/bin/activate
uv pip install -e ".[dev]"                # or:  pip install -e ".[dev]"
jobhunt app
```

### Option 4: Docker

```bash
git clone https://github.com/Abdalla2004-collab/Jobhunt
cd jobhunt
docker compose up --build -d
# open http://127.0.0.1:8765
```

### Optional desktop integration

On Linux, add jobhunt to your application launcher:

```bash
bash packaging/install-desktop-entry.sh
```

On macOS, use Automator to wrap `jobhunt app` as an Application.
On Windows, the binary can be pinned to the Start menu after first launch.

### Where your data lives

| OS      | Path                                         |
|---------|----------------------------------------------|
| Linux   | `~/.local/share/jobhunt/`                    |
| macOS   | `~/Library/Application Support/jobhunt/`     |
| Windows | `%APPDATA%\jobhunt\`                         |

When run from a source checkout with a `./data/` directory, it'll use that
instead. Run `jobhunt info` any time to see the resolved paths.

## Day-to-day use

```bash
jobhunt app              # start UI + open browser (one-shot launch)
jobhunt app --schedule 360   # ...with self-update every 6 hours

jobhunt scrape           # one-off scrape from the CLI
jobhunt stats            # quick counts
jobhunt list-sources     # what's configured
jobhunt check-alerts     # manually fire alert check
jobhunt match-cv my.pdf  # upload CV + score all jobs (needs [match] extra)
jobhunt info             # show paths
```

## Features

### Filters

| Filter        | What it does |
|---------------|--------------|
| keyword       | free text across title, company, description |
| company       | substring of company name |
| location      | substring of location |
| work mode     | remote, hybrid, onsite |
| level         | intern, entry, junior, mid, senior, staff, principal, lead |
| degree        | none, bachelors, masters, phd |
| max years     | excludes jobs whose minimum YoE exceeds this |
| languages     | repeated tag filter — `python`, `go`, `typescript`, … |
| skills        | repeated tag filter — `react`, `aws`, `kubernetes`, … |
| posted within | 1 / 7 / 14 / 30 days |
| min CV match  | when a CV is loaded, hide anything below the threshold |
| sort          | relevance / posted date / last seen / CV match |

All filters are server-side SQL, all changes are HTMX-driven so the page never
reloads.

### CV semantic match (optional)

```bash
uv pip install -e ".[match]"   # adds sentence-transformers (~500MB of deps)
```

Then visit `/cv` and upload a PDF, DOCX, or TXT. Your CV is parsed locally,
embedded with `sentence-transformers/all-MiniLM-L6-v2` on CPU (small, fast,
free), and stored only in your local SQLite. Each job in your DB is then
scored by cosine similarity against your CV. Sort or filter by match.

### Saved searches + desktop alerts

Visit `/alerts` to define named filter sets (e.g. *London Python remote ≤ 3y*).
After every scrape — manual or scheduled — new matches fire a desktop
notification via `notify-send` (Linux), `osascript` (macOS), or PowerShell
(Windows). Each posting is notified at most once.

### Self-update (free, local, safe)

Set `JOBHUNT_REFRESH_INTERVAL_MINUTES` and the server starts an in-process
APScheduler that re-scrapes on that interval. No external cron, no extra
processes.

```bash
JOBHUNT_REFRESH_INTERVAL_MINUTES=360 jobhunt serve
# or
jobhunt serve --schedule 360
```

### Per-source health page

`/health` shows the latest run of every configured board with status badges
(healthy / stale / failing) plus the scheduler state. Broken sources are
obvious at a glance.

## CLI

```bash
jobhunt scrape         # one-off scrape + dedup + stale sweep
jobhunt serve          # start UI (default http://127.0.0.1:8765)
jobhunt stats          # quick counts by source + last run info
jobhunt match-cv FILE  # upload + match a CV from the command line
jobhunt check-alerts   # manually trigger alert check
jobhunt list-sources   # show configured sources
```

## Privacy & safety

- Everything runs locally; the SQLite DB lives in `./data/jobhunt.db`.
- `data/`, `.env`, and `local_sources.yaml` are gitignored.
- The scraper only reads. No clicks, form fills, or POSTs to job sites.
- Sets a polite `User-Agent` and limits concurrency (default 4).
- CV processing never leaves the machine; embedding model is local.
- Web UI sets strict CSP (`script-src 'self'`), `X-Frame-Options DENY`,
  `X-Content-Type-Options nosniff`, `Referrer-Policy same-origin`.
- Docker container binds to `127.0.0.1` only (never exposed to the network).
- HTMX is vendored locally — no CDN dependency.

## Configuration

Copy `.env.example` to `.env` and edit. All settings have working defaults.

| Env var                              | Default          | Notes |
|--------------------------------------|------------------|-------|
| `JOBHUNT_DB_PATH`                    | `./data/jobhunt.db` | |
| `JOBHUNT_USER_AGENT`                 | `jobhunt/0.1 …`  | Sent to all scrape targets |
| `JOBHUNT_REQUEST_TIMEOUT`            | `20`             | seconds per HTTP call |
| `JOBHUNT_CONCURRENCY`                | `4`              | max parallel scrapers |
| `JOBHUNT_STALE_AFTER_DAYS`           | `14`             | drop jobs unseen for this long |
| `JOBHUNT_HOST` / `JOBHUNT_PORT`      | `127.0.0.1:8765` | |
| `JOBHUNT_REFRESH_INTERVAL_MINUTES`   | `0` (off)        | set > 0 to enable self-update |
| `JOBHUNT_NOTIFY_METHOD`              | `auto`           | desktop notification method |
| `JOBHUNT_NOTIFY_BATCH_MAX`           | `5`              | alerts per cycle |

To customize the list of companies, create `src/jobhunt/local_sources.yaml`
(gitignored) using the same shape as `sources.yaml`. Entries there merge with
the defaults.

## How dedup works

Each job's identity is `sha256(normalized(company, title, location))` truncated
to 32 chars. The normalizer strips seniority words, parenthetical noise, and
common company suffixes — so *Sr. Backend Engineer (Remote)* at Acme Inc
collapses with *Backend Engineer* at Acme Corp in the same location, even
across two sources.

A separate `description_hash` is stored to enable near-duplicate detection
across sources in future versions.

## Tests

```bash
pytest
```

20+ tests covering dedup, extractors, every scraper (with mocked HTTP), CV
parsing, and cosine similarity.

## Architecture

```
src/jobhunt/
├── main.py            # FastAPI app, security headers, all routes
├── cli.py             # typer CLI
├── config.py          # pydantic-settings, all env-tunable
├── db.py              # SQLAlchemy engine + forward-only migrations
├── models.py          # Job, ScrapeRun, SavedSearch, CVProfile
├── filters.py         # JobQuery + SQL builder + facets
├── refresh.py         # scrape pipeline, dedup, stale sweep
├── scoring.py         # transparent relevance score
├── extract.py         # skill/level/remote/YoE regex extractors
├── dedup.py           # fingerprint + normalization
├── scheduler.py       # APScheduler self-update
├── notifications.py   # cross-platform desktop notify
├── alerts.py          # saved-search alert engine
├── cv.py              # CV parse + embed + match
├── scrapers/          # 9 source adapters
├── templates/         # Jinja2 — masthead, search, alerts, cv, health
├── static/            # style.css, app.js, htmx.min.js (vendored)
└── sources.yaml       # default list of boards
```

## Roadmap

- More ATS slugs in the default list (pre-curated, manually verified).
- Cross-source near-duplicate detection (description fingerprint match).
- Salary range extraction.
- CV → suggested filters page (one-click prefill from your profile).
- Markdown/PDF export of saved searches.

## License

MIT.
