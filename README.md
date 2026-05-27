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

Pick whichever feels easier. Both take under a minute.

### Option A: Download and double-click

No terminal needed. Download the file for your computer, open it, done.

<div align="center">
<table>
<tr>
<td align="center" width="33%">

**Windows**

[Download jobhunt.exe](https://github.com/Abdalla2004-collab/Jobhunt/releases/latest/download/jobhunt-windows-x86_64.exe)

</td>
<td align="center" width="33%">

**macOS**

[Download jobhunt](https://github.com/Abdalla2004-collab/Jobhunt/releases/latest/download/jobhunt-macos-arm64)

</td>
<td align="center" width="33%">

**Linux**

[Download jobhunt](https://github.com/Abdalla2004-collab/Jobhunt/releases/latest/download/jobhunt-linux-x86_64)

</td>
</tr>
</table>
</div>

Double-click the file. Your browser opens to jobhunt. That's it.

> Your OS may show a security prompt ("unrecognized publisher") — this
> happens with every free open-source app. It's not a malware warning.
> Click **More info → Run anyway** (Windows) or **Open** (macOS).

### Option B: One-line install (recommended, auto-updates)

**Linux / macOS:**
```bash
curl -fsSL https://raw.githubusercontent.com/Abdalla2004-collab/Jobhunt/main/scripts/install.sh | bash
```

**Windows (PowerShell):**
```powershell
irm https://raw.githubusercontent.com/Abdalla2004-collab/Jobhunt/main/scripts/install.ps1 | iex
```

Then run `jobhunt`. Your browser opens. That's it.

This installs via **[uv](https://github.com/astral-sh/uv)** — a trusted,
open-source package manager (40k+ GitHub stars). Everything goes in its own
isolated environment. Nothing touches your system. You can
[read the script](scripts/install.sh) before running it.

### Updating

```
jobhunt update
```

### Uninstalling

```
uv tool uninstall jobhunt
```

Removes jobhunt and its isolated environment. Nothing else is touched.

### What happens on first launch

A friendly empty page that says **"Your paper is blank."** Click the big
**Pull listings now** button. The app reaches out to a handful of public
company career pages and pulls down ~5,000 real job postings. Takes about a
minute.

After that, the filters do the rest. Sort by relevance, narrow to remote roles,
add language tags, set a maximum years of experience — all without a page
reload.

### Is it safe?

Short answer: yes. Specifically:

- **Everything runs on your machine.** No data is sent anywhere — not to me,
  not to any analytics service.
- **The whole source code is here.** You can read every line.
- **It only ever reads from job-board APIs.** It never logs into anything, never
  fills a form, never posts.
- **The web page is bound to `127.0.0.1`** — your laptop only, not your network.
- **Released under MIT.** Use it, modify it, share it.

### Other ways to install

<details>
<summary>Already have uv or pipx?</summary>

```bash
uv tool install git+https://github.com/Abdalla2004-collab/Jobhunt.git
# or
pipx install git+https://github.com/Abdalla2004-collab/Jobhunt.git
```

Update: `uv tool upgrade jobhunt` or `pipx upgrade jobhunt`.

</details>

<details>
<summary>Prefer Docker?</summary>

```bash
git clone https://github.com/Abdalla2004-collab/Jobhunt
cd Jobhunt
docker compose up --build -d
# open http://127.0.0.1:8765
```

Update: `git pull && docker compose up --build -d`.

</details>

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

> Run `jobhunt` and visit `http://127.0.0.1:8765`. Five pages: Search,
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
jobhunt                  # start UI + open browser (this is the main one)
jobhunt --schedule 360   # also refresh every 6 hours in the background
jobhunt update           # update to the latest version

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

To enable CV-aware ranking, reinstall with the match extra:
```bash
uv tool install --reinstall "git+https://github.com/Abdalla2004-collab/Jobhunt.git[match]"
```

This adds sentence-transformers (~500 MB one-time download). Then open the
**CV Match** tab and upload a PDF, DOCX, or TXT. The CV is
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

## Automatic job refresh

```bash
jobhunt --schedule 360
```

Runs the app and re-scrapes all sources every 6 hours in the background.
No cron job needed — an in-process scheduler handles it while the app is open.

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
jobhunt
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
