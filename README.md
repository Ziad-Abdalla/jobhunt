<div align="center">
  <img src="packaging/jobhunt.svg" alt="jobhunt" width="180" />

# jobhunt

**A quiet job paper for your machine.**

Search thousands of real software engineering openings — from real
company career pages — with strong filters, optional CV-aware ranking,
and zero data leaving your computer.

[Install](#install) · [Features](#what-it-does) · [How it works](#how-it-works) · [Privacy](#privacy)
</div>

---

## Install

<div align="center">

### Click your operating system to download

<table>
<tr>
<td align="center" width="33%">

**Windows**

[**⬇ Download jobhunt.exe**](https://github.com/Abdalla2004-collab/Jobhunt/releases/latest/download/jobhunt-windows-x86_64.exe)

Then double-click it.

</td>
<td align="center" width="33%">

**macOS** (Apple Silicon)

[**⬇ Download jobhunt**](https://github.com/Abdalla2004-collab/Jobhunt/releases/latest/download/jobhunt-macos-arm64)

Then run it (see below).

</td>
<td align="center" width="33%">

**Linux** (x86_64)

[**⬇ Download jobhunt**](https://github.com/Abdalla2004-collab/Jobhunt/releases/latest/download/jobhunt-linux-x86_64)

Then run it (see below).

</td>
</tr>
</table>

</div>

### After you've downloaded it

**Windows:** double-click `jobhunt.exe`. The first time, Windows SmartScreen will say
"unrecognized publisher" — click **More info → Run anyway**. That's normal for any
open-source app that isn't paying for code-signing.

**macOS:** open Terminal, then run:
```bash
cd ~/Downloads
chmod +x jobhunt-macos-arm64
xattr -d com.apple.quarantine jobhunt-macos-arm64    # bypasses Gatekeeper for this file
./jobhunt-macos-arm64 app
```

**Linux:** open Terminal, then run:
```bash
cd ~/Downloads
chmod +x jobhunt-linux-x86_64
./jobhunt-linux-x86_64 app
```

`jobhunt app` starts a tiny server on your machine and opens the page in your
browser. Click **Refresh sources** in the top bar and wait about a minute for
the first pull. That's it.

### Or — install with one command (Terminal users)

Linux / macOS:
```bash
curl -fsSL https://raw.githubusercontent.com/Abdalla2004-collab/Jobhunt/main/scripts/install.sh | bash
jobhunt app
```

Windows PowerShell:
```powershell
irm https://raw.githubusercontent.com/Abdalla2004-collab/Jobhunt/main/scripts/install.ps1 | iex
jobhunt app
```

These scripts auto-detect your OS, download the right binary, install it to
`~/.local/bin` (or `%USERPROFILE%\jobhunt\`), and tell you what to do next.

### Or — if you have Python or Docker

```bash
# Python users
pipx install git+https://github.com/Abdalla2004-collab/Jobhunt.git && jobhunt app
```

```bash
# Docker users
git clone https://github.com/Abdalla2004-collab/Jobhunt
cd Jobhunt
docker compose up --build -d   # then open http://127.0.0.1:8765
```

---

## What it does

- Searches across **9 real job boards**: Greenhouse, Lever, Ashby, Workable,
  SmartRecruiters, Recruitee, Workday, RemoteOK, and Hacker News' monthly
  "Who is Hiring?" thread.
- Strong filters: keyword, company, location, work mode (remote/hybrid/onsite),
  level (intern → principal), degree required, max years of experience,
  programming languages, skills, posted within N days, and a CV-match score.
- **CV match** (optional): drop in your PDF/DOCX/TXT and every job gets a
  similarity score. Sort by match. Filter to ≥ 70 %. Stop scrolling junk.
- **Saved searches**: define a filter set once, get a desktop notification
  whenever a new matching job appears. Each posting is alerted at most once.
- **Self-updating**: tell it to refresh every N minutes; it runs in the
  background while the app is open. No cron jobs.
- **Add your own companies**: pop over to the Sources tab and add any
  company's career-page slug. No YAML editing required.

## Screenshots

> Run `jobhunt app` and visit `http://127.0.0.1:8765`. Five pages: Search,
> Alerts, CV Match, Sources, Source Health.

## How it works

Companies that hire publicly use applicant-tracking systems (ATS) like
Greenhouse, Lever, and Ashby. Their career pages are powered by stable,
public JSON APIs that anyone is allowed to call. jobhunt is just a friendly
client over those APIs, with a local database, a search UI, and a CV matcher
on top.

It does **not** scrape LinkedIn or Indeed. Their terms forbid it, and their
anti-bot defences break unofficial scrapers every few weeks. If you really
want LinkedIn coverage, install the opt-in `[linkedin]` extra — the README
explains the trade-offs.

## Privacy

- Everything stays on your machine. Nothing is uploaded anywhere.
- Your SQLite database, your CV, and your alert history all live in
  `~/.local/share/jobhunt/` (Linux), `~/Library/Application Support/jobhunt/`
  (macOS), or `%APPDATA%\jobhunt\` (Windows).
- The web UI binds to `127.0.0.1` only — never reachable from your network.
- No telemetry. No analytics. No update pings.
- A polite `User-Agent` is sent to job-board APIs so we're identifiable
  rather than sneaky.

## Day-to-day commands

```bash
jobhunt app              # start UI + open browser (this is the main one)
jobhunt app --schedule 360   # also refresh every 6 hours in the background

jobhunt scrape           # one-off scrape from the CLI
jobhunt stats            # quick counts by source
jobhunt list-sources     # what's configured
jobhunt check-alerts     # manually fire alert check now
jobhunt match-cv my.pdf  # upload CV + score all jobs (needs [match] extra)
jobhunt info             # show paths
jobhunt --version
```

## Filters in detail

| Filter        | What it does |
|---------------|--------------|
| keyword       | free text across title, company, description |
| company       | substring of company name |
| location      | substring of location |
| work mode     | remote / hybrid / onsite |
| level         | intern, entry, junior, mid, senior, staff, principal, lead |
| degree        | none, bachelors, masters, phd |
| max years     | excludes jobs whose minimum YoE exceeds this |
| languages     | comma list — `python`, `go`, `typescript`, … |
| skills        | comma list — `react`, `aws`, `kubernetes`, … |
| posted within | 1 / 7 / 14 / 30 days |
| min CV match  | when a CV is loaded, hide anything below the threshold |
| sort          | relevance / posted date / last seen / CV match |

## CV match (optional)

```bash
uv pip install -e ".[match]"   # adds sentence-transformers, ~500 MB
```

Then open the **CV Match** tab and upload a PDF, DOCX, or TXT. The CV is
parsed locally and embedded with `sentence-transformers/all-MiniLM-L6-v2`
on CPU. Every job in your database gets a cosine similarity score against
your CV. Sort or filter by match. Nothing ever leaves your machine.

## About LinkedIn / Indeed

There is **no free legitimate LinkedIn API**. LinkedIn killed third-party
access in 2015. The unofficial `linkedin-api` and JobSpy's LinkedIn scraper
use your account's session cookie and **risk a permanent account ban**.
jobhunt keeps LinkedIn strictly opt-in via the `[linkedin]` extra.

## Where your data lives

| OS      | Path                                         |
|---------|----------------------------------------------|
| Linux   | `~/.local/share/jobhunt/`                    |
| macOS   | `~/Library/Application Support/jobhunt/`     |
| Windows | `%APPDATA%\jobhunt\`                         |

Run `jobhunt info` any time to see the resolved paths.

## Self-update

```bash
jobhunt app --schedule 360
# or:
JOBHUNT_REFRESH_INTERVAL_MINUTES=360 jobhunt serve
```

An in-process scheduler re-scrapes on the interval. No cron job needed.

## Safety

- Strict Content Security Policy (`script-src 'self'`).
- CSRF defence: cross-origin POSTs to `127.0.0.1` are rejected.
- HTMX vendored locally — no CDN dependency.
- `X-Frame-Options DENY`, `X-Content-Type-Options nosniff`,
  `Referrer-Policy same-origin`.
- Read-only scraping. The app never POSTs or clicks anything on job sites.

## For developers

Full development guide in [`CONTRIBUTING.md`](CONTRIBUTING.md).

```bash
git clone https://github.com/Abdalla2004-collab/Jobhunt
cd Jobhunt
uv venv && source .venv/bin/activate
uv pip install -e ".[dev,match]"
pytest -q
jobhunt app --schedule 0
```

## Architecture

```
src/jobhunt/
├── main.py            FastAPI app, security headers, routes
├── cli.py             typer CLI (jobhunt app/serve/scrape/...)
├── config.py          pydantic-settings, OS-correct data dir
├── db.py              SQLAlchemy engine + forward-only migrations
├── models.py          Job, ScrapeRun, SavedSearch, CVProfile
├── filters.py         JobQuery + SQL builder + facets
├── refresh.py         scrape pipeline, dedup, stale sweep
├── scoring.py         transparent relevance score
├── extract.py         skill/level/remote/YoE extractors
├── dedup.py           fingerprint + normalization
├── scheduler.py       APScheduler self-update
├── notifications.py   cross-platform desktop notify
├── alerts.py          saved-search alert engine
├── cv.py              CV parse + embed + cosine match
├── sources_admin.py   in-UI source management
├── scrapers/          9 source adapters
├── templates/         Jinja2 — masthead + 5 pages
├── static/            style.css, app.js, htmx.min.js (vendored)
└── sources.yaml       default board list
```

## Tests

```bash
pytest -q     # 37 tests
```

Includes a real end-to-end CV pipeline test with three synthetic CVs
(junior Python, senior ML, frontend React) against a synthetic job corpus.
Each CV correctly ranks its expected role at #1.

## License

MIT — see [`LICENSE`](LICENSE).
