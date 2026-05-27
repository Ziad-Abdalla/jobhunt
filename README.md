<div align="center">
  <img src="packaging/jobhunt.svg" alt="jobhunt" width="180" />

# jobhunt

**Search thousands of real job openings — locally, privately, with great filters.**

No account needed. No data leaves your machine.

<br>

**[Get jobhunt](https://abdalla2004-collab.github.io/Jobhunt/)** — auto-detects your OS, one command to install.

<br>

Or install right now:

```
pip install jobhunt-app && jobhunt
```

</div>

---

## What it does

- **17 job boards**: Greenhouse, Lever, Ashby, Workable, SmartRecruiters,
  Recruitee, Workday, RemoteOK, HackerNews, SimplifyJobs, Arbeitnow, Jobicy,
  Himalayas, TheMuse, Arbeitsagentur, Jooble, Reed
- **15 filters**: keyword, company, location, remote/hybrid/onsite, level,
  job type, salary, degree, experience, languages, skills, date, visa, CV match, sort
- **Salary on every job**: real data + self-calibrating estimator
- **CV match**: upload your CV, sort jobs by fit
- **Saved searches**: desktop notifications on new matching jobs
- **Auto-refresh**: re-scrape in the background every N hours
- **Settings page**: update, clear data, and uninstall from the UI

## Install

**Windows** (open PowerShell, paste this):
```powershell
irm https://raw.githubusercontent.com/Abdalla2004-collab/Jobhunt/main/scripts/install.ps1 | iex
```

**macOS / Linux** (open Terminal, paste this):
```bash
curl -fsSL https://raw.githubusercontent.com/Abdalla2004-collab/Jobhunt/main/scripts/install.sh | bash
```

**Already have pip?**
```bash
pip install jobhunt-app
```

Then run `jobhunt`. Your browser opens. That's it.

### Manage

| Action | How |
|--------|-----|
| **Update** | `jobhunt update` or Settings tab > Check for updates |
| **Uninstall** | `uv tool uninstall jobhunt-app` or see Settings tab |
| **Clear data** | Settings tab > Clear all jobs |
| **Auto-refresh** | `jobhunt --schedule 360` (every 6 hours) |
| **Check sources** | `jobhunt doctor` |

## How it works

Companies use applicant-tracking systems (Greenhouse, Lever, Ashby, etc.)
with stable public APIs. jobhunt reads from those APIs, stores everything
locally, and gives you a search UI with filters and a CV matcher.

Does **not** scrape LinkedIn or Indeed.

## Privacy

Everything runs on your machine. No telemetry, analytics, or update pings.
The UI only listens on `127.0.0.1`. Your data is stored locally:

| OS | Path |
|----|------|
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

See [`CONTRIBUTING.md`](CONTRIBUTING.md).

## License

MIT
