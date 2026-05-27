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

Takes under a minute. Pick your platform:

### Windows

**Option A — Double-click installer (easiest):**

[Download install-windows.bat](https://github.com/Abdalla2004-collab/Jobhunt/releases/latest/download/install-windows.bat) — double-click it. It installs everything and opens jobhunt in your browser.

**Option B — One-liner in PowerShell:**
```powershell
irm https://raw.githubusercontent.com/Abdalla2004-collab/Jobhunt/main/scripts/install.ps1 | iex
```
Then run `jobhunt`.

### macOS / Linux

```bash
curl -fsSL https://raw.githubusercontent.com/Abdalla2004-collab/Jobhunt/main/scripts/install.sh | bash
```
Then run `jobhunt`.

### Already have pip, uv, or pipx?

```bash
pip install jobhunt
# or
uv tool install jobhunt
# or
pipx install jobhunt
```

Then run `jobhunt`.

### Updating

```
jobhunt update
```

Or open the **Settings** tab in the web UI and click **Check for updates**.

### Uninstalling

```
uv tool uninstall jobhunt
```

Or check the **Settings** tab — it shows the exact command for your setup.

### What happens on first launch

An empty page with a big **Pull listings now** button. Click it. jobhunt
reaches out to public company career pages and pulls down thousands of real
job postings. Takes about a minute.

After that, use the filters on the left — remote only, salary minimum,
specific languages, experience level — all without a page reload.

### Is it safe?

- **Everything runs on your machine.** No data is sent anywhere.
- **The whole source code is here.** MIT licensed.
- **It only reads from job-board APIs.** Never logs in, fills forms, or posts.
- **The web page is bound to `127.0.0.1`** — your laptop only, not your network.

### Other ways to install

<details>
<summary>Docker</summary>

```bash
git clone https://github.com/Abdalla2004-collab/Jobhunt
cd Jobhunt
docker compose up --build -d
# open http://127.0.0.1:8765
```

</details>

<details>
<summary>Troubleshooting</summary>

**"command not found" after install:**
Add `~/.local/bin` to your PATH:
```bash
export PATH="$HOME/.local/bin:$PATH"
```
Add that line to `~/.bashrc` or `~/.zshrc` and reopen your terminal.

**Windows: "irm is not recognized":**
Use PowerShell (not Command Prompt). Search for "PowerShell" in Start.

**Windows: "execution of scripts is disabled":**
```powershell
Set-ExecutionPolicy RemoteSigned -Scope CurrentUser
```

</details>

---

## What it does

- Searches across **17 job board adapters**: Greenhouse, Lever, Ashby, Workable,
  SmartRecruiters, Recruitee, Workday, RemoteOK, HackerNews, SimplifyJobs,
  Arbeitnow, Jobicy, Himalayas, TheMuse, Arbeitsagentur (Germany), Jooble
  (69 countries), and Reed.co.uk (UK).
- **15 filters**: keyword, company, location, work mode (remote/hybrid/onsite),
  level (intern to principal), job type, minimum salary, degree, max years of
  experience, programming languages, skills, posted within, visa sponsorship,
  CV match score, and sort order. All stackable.
- **Salary on every job**: 100% salary coverage — real salary data where
  available, plus a self-calibrating estimator for the rest.
- **CV match** (optional): upload your CV and every job gets a similarity score.
- **Saved searches**: get desktop notifications when new matching jobs appear.
- **Auto-refresh**: set it to re-scrape every N hours in the background.
- **Add your own companies**: use the Sources tab — no file editing needed.
- **Settings page**: update, clear data, and uninstall — all from the UI.

## Screenshots

> Run `jobhunt` and visit `http://127.0.0.1:8765`. Six pages: Search,
> Alerts, CV Match, Sources, Source Health, Settings.

## How it works

Companies use applicant-tracking systems (ATS) like Greenhouse, Lever, and
Ashby. Their career pages have stable, public JSON APIs. jobhunt is a
friendly client over those APIs, with a local database, search UI, and CV
matcher on top.

It does **not** scrape LinkedIn or Indeed (their terms forbid it).

## Privacy

- Everything stays on your machine. Nothing is uploaded anywhere.
- No telemetry. No analytics. No update pings.
- The web UI binds to `127.0.0.1` only — never reachable from your network.

### Where your data lives

| OS      | Path                                         |
|---------|----------------------------------------------|
| Linux   | `~/.local/share/jobhunt/`                    |
| macOS   | `~/Library/Application Support/jobhunt/`     |
| Windows | `%APPDATA%\jobhunt\`                         |

Run `jobhunt info` to see the resolved paths.

## Commands

```bash
jobhunt                  # start + open browser
jobhunt --schedule 360   # also refresh every 6 hours
jobhunt update           # update to latest version
jobhunt doctor           # check which sources are working
jobhunt scrape           # one-off scrape from CLI
jobhunt stats            # job counts by source
jobhunt match-cv my.pdf  # upload CV + score all jobs
jobhunt info             # show file paths
jobhunt --version
```

## For developers

Full guide in [`CONTRIBUTING.md`](CONTRIBUTING.md).

```bash
git clone https://github.com/Abdalla2004-collab/Jobhunt
cd Jobhunt
uv venv && source .venv/bin/activate
uv pip install -e ".[dev]"
pytest -q
jobhunt
```

## Tests

```bash
pytest -q          # 69 unit tests
pytest -m e2e      # 11 browser E2E tests (needs Playwright)
```

## License

MIT — see [`LICENSE`](LICENSE).
