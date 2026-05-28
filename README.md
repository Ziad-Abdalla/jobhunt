<div align="center">
  <img src="packaging/jobhunt.svg" alt="jobhunt" width="180" />

# jobhunt

**24,000+ software jobs. 4 sections. Clean filters. Runs locally.**

No account needed. No data leaves your machine. Free and open source.

</div>

---

## Install

**Windows** — open PowerShell, paste this:
```powershell
irm https://raw.githubusercontent.com/Abdalla2004-collab/Jobhunt/main/scripts/install.ps1 | iex
```

**macOS / Linux** — open Terminal, paste this:
```bash
curl -fsSL https://raw.githubusercontent.com/Abdalla2004-collab/Jobhunt/main/scripts/install.sh | bash
```

Then type `jobhunt` in any terminal. Your browser opens automatically.

**Or with pip:**
```
pip install jobhunt-app
jobhunt
```

---

## 4 Sections

### Jobs (main search)
All 24,000+ software roles from 130+ company boards and 17 job sources.
Filters: keyword, company, location, remote/hybrid/onsite, level, job type,
salary, degree, experience, languages, skills, posted date, visa sponsorship,
CV match, sort order.

### Local Jobs
Entry-level and junior roles near you. Type your city (London, Whitechapel,
Stuttgart, Berlin, Manchester, etc.) and filter by level, job type, max
experience (0-5 years), and salary. Focused on UK and Germany.

### Freelance & Contract
Contract, freelance, and temporary software roles. Filter by keyword, work
mode, and salary. Sorted by most recently posted.

### Bug Bounty
871 active bug bounty programs from HackerOne, Bugcrowd, Intigriti, and
YesWeHack. Search by company or domain. Filter by platform.

---

## Features

- **17 job board adapters**: Greenhouse, Lever, Ashby, Workable, SmartRecruiters,
  Recruitee, Workday, RemoteOK, HackerNews, SimplifyJobs, Arbeitnow, Jobicy,
  Himalayas, TheMuse, Arbeitsagentur (Germany), Jooble (69 countries), Reed (UK)
- **Intern/junior focused**: 3,300+ entry-level roles. Detects intern, graduate,
  trainee, apprentice, co-op, Ausbildung, Werkstudent, and "0-1 years" patterns.
- **Salary on every job**: real data where available, plus a self-calibrating estimator.
- **CV match**: upload your CV and sort jobs by how well they fit your experience.
- **Saved search alerts**: desktop notifications when new matching jobs appear.
- **Settings page**: update, clear data, enter API keys, uninstall — all from the UI.
- **Auto-refresh**: re-scrape every N hours in the background.

## Manage

| What | How |
|------|-----|
| **Launch** | Type `jobhunt` in any terminal — browser opens automatically |
| **Update** | Settings tab > Check for updates, or re-run the install command |
| **Clear jobs** | Settings tab > Clear all jobs |
| **Add API keys** | Settings tab > Jooble / Reed keys (optional, unlocks more sources) |
| **Uninstall** | Settings tab shows the command, or `uv tool uninstall jobhunt-app` |
| **Auto-refresh** | `jobhunt --schedule 360` (every 6 hours) |
| **Check sources** | `jobhunt doctor` |

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

69 unit tests + 11 Playwright E2E tests. See [`CONTRIBUTING.md`](CONTRIBUTING.md).

## License

MIT
