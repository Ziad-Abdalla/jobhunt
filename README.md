<div align="center">
  <img src="packaging/jobhunt.svg" alt="jobhunt" width="180" />

# jobhunt

**Thousands of jobs. 3 sections. Clean filters. Runs locally.**

No account needed. No data leaves your machine. Free and open source.

</div>

---

## Install

**Windows** — open PowerShell (search "PowerShell" in Start), paste this:
```powershell
irm https://raw.githubusercontent.com/Abdalla2004-collab/Jobhunt/main/scripts/install.ps1 | iex
```
A `jobhunt` shortcut appears on your Desktop and in Start Menu. Click it to launch.

**macOS / Linux** — open Terminal, paste this:
```bash
curl -fsSL https://raw.githubusercontent.com/Abdalla2004-collab/Jobhunt/main/scripts/install.sh | bash
```
Then type `jobhunt`. Your browser opens automatically.

**Or with pip:**
```
pip install jobhunt-app
jobhunt
```

---

## 3 Sections

### Jobs (main search)
Thousands of software roles from 130+ company boards.
Filters: keyword, company, location, remote/hybrid/onsite, remote eligibility
(worldwide-friendly vs US/EU/UK-only), level, job type, salary, degree,
experience, languages, skills, posted date, visa sponsorship, CV match,
sort order.

Egypt coverage via Wuzzuf is fully filterable: extraction understands Arabic
job postings (level, job type, remote, years of experience), estimates Cairo
salaries in EGP, and renders Arabic titles right-to-left.

### Local Jobs
Zero-experience local work near you — cleaning, retail, warehouse, hospitality,
care, customer service, driving, reception, security. Type your city
(Whitechapel, Manchester, Stuttgart, Berlin) and the page defaults to
no-experience non-tech roles; flip the *What kind of work* dropdown to switch
to tech / software or "any kind". Best UK and Germany coverage; Arbeitsagentur (German Federal
Employment Agency) is free and no API key needed.

### Freelance & Contract
Contract, freelance, and temporary software roles. Filter by keyword, work
mode, and salary. Sorted by most recently posted.

### Apply
Where does applying actually happen? Every job's apply link is classified:
**ATS form** (a structured, hosted form — Greenhouse, Lever, Ashby, Workday, …),
**job board** (you apply on the board itself — sometimes with a board
account, like Wuzzuf — or its listing points on to the real form), or
**company site** (an arbitrary form on the company's own site). Filter the
ranked list by application flow and pick targets by effort.

Queue jobs you want to apply to, keep your applicant details in a local-only
profile, and let a local assistant draft applications — every draft is shown
for your review and **nothing is ever submitted without your approval**.
Your profile never leaves your machine (loopback-only endpoints, export API
off by default, no passport/ID fields, credential-paste rejection).

---

## Features

- **22 job board adapters**: Greenhouse, Lever, Ashby, Workable, SmartRecruiters,
  Recruitee, Workday, RemoteOK, HackerNews, SimplifyJobs, Arbeitnow, Jobicy,
  Himalayas, TheMuse, Arbeitsagentur (Germany — all sectors, no key),
  Jooble (69 countries), Reed (UK — all sectors, broad keyword set),
  Wuzzuf (Egypt — all sectors, no key), Remotive, Working Nomads,
  We Work Remotely, python.org Jobs
- **Intern/junior focused**: 3,300+ entry-level roles. Detects intern, graduate,
  trainee, apprentice, co-op, Ausbildung, Werkstudent, and "0-1 years" patterns.
- **Salary on every job**: real data where available, plus a self-calibrating estimator.
- **CV match**: upload your CV and sort jobs by how well they fit your experience.
  Works without any extra install — keyword overlap by default, free
  semantic-similarity upgrade via `jobhunt-app[match]`. Once loaded, the default
  relevance sort blends the match score automatically; set
  `JOBHUNT_USER_LOCATION` and geo-restricted jobs you can't apply to sink too.
- **Saved search alerts**: desktop notifications when new matching jobs appear.
- **Settings page**: update, clear data, enter API keys, uninstall — all from the UI.
- **Auto-refresh**: re-scrape every N hours in the background.

## Manage

| What | How |
|------|-----|
| **Launch** | Click `jobhunt` on Desktop or Start Menu (Windows), or type `jobhunt` in terminal |
| **Update** | Settings tab > Check for updates, or re-run the install command |
| **Clear jobs** | Settings tab > Clear all jobs |
| **Add API keys** | Settings tab > Jooble / Reed keys (optional, unlocks more sources) |
| **Uninstall** | Settings tab → **Uninstall jobhunt** button (one click) |
| **Auto-refresh** | `jobhunt --schedule 360` (every 6 hours) |
| **Check sources** | `jobhunt doctor` (or `--json` for scripts) |
| **Backup data** | `jobhunt backup` — saved searches + CV + local sources to a zip |
| **Restore data** | `jobhunt restore <backup.zip>` |

## How it works

Companies use applicant-tracking systems (Greenhouse, Lever, Ashby, etc.)
with public APIs. jobhunt reads from those APIs, stores everything locally,
and gives you a search UI with filters and a CV matcher.

Does **not** scrape LinkedIn or Indeed.

## Privacy

Everything runs on your machine. No telemetry, analytics, or update pings.
The UI only listens on `127.0.0.1` (your machine, not your network).

| OS | Data stored at |
|----|---------------|
| Windows | `%APPDATA%\jobhunt\` |
| macOS | `~/Library/Application Support/jobhunt/` |
| Linux | `~/.local/share/jobhunt/` |

## For developers

```bash
git clone https://github.com/Abdalla2004-collab/Jobhunt && cd Jobhunt
uv venv && source .venv/bin/activate
uv pip install -e ".[dev]"
pytest -q && jobhunt
```

100+ unit tests + 11 Playwright E2E tests. See [`CONTRIBUTING.md`](CONTRIBUTING.md).

## License

MIT
