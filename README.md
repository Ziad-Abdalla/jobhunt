<div align="center">
  <img src="packaging/jobhunt.svg" alt="jobhunt" width="180" />

# jobhunt

**Search thousands of real job openings — locally, privately, with great filters.**

No account needed. No data leaves your machine. Just download, run, and search.

[Features](#what-it-does) · [How it works](#how-it-works) · [Privacy](#privacy)
</div>

---

## Download

Pick your system. One click installs everything and opens jobhunt in your browser.

<div align="center">
<table>
<tr>
<th align="center" width="33%">Windows</th>
<th align="center" width="33%">macOS</th>
<th align="center" width="33%">Linux</th>
</tr>
<tr>
<td align="center">

**[Download for Windows](https://github.com/Abdalla2004-collab/Jobhunt/releases/latest/download/install-windows.bat)**

Double-click the file.

</td>
<td align="center">

**[Download for Mac](https://github.com/Abdalla2004-collab/Jobhunt/releases/latest/download/install-mac.command)**

Double-click the file.

</td>
<td align="center">

**[Download for Linux](https://github.com/Abdalla2004-collab/Jobhunt/releases/latest/download/install-linux.sh)**

Run: `bash install-linux.sh`

</td>
</tr>
</table>
</div>

Each installer is a tiny script (~1 KB) that installs [uv](https://github.com/astral-sh/uv)
(a trusted package manager), then installs jobhunt from [PyPI](https://pypi.org/project/jobhunt-app/),
and opens it. You can [read the source](scripts/) before running.

> **Windows note:** You may see "Windows protected your PC" — click
> **More info > Run anyway**. This is normal for any script not from the Microsoft Store.

### Alternative: one-line terminal install

```bash
pip install jobhunt-app && jobhunt
```

Or with uv/pipx:
```bash
uv tool install jobhunt-app && jobhunt
```

### Updating

```
jobhunt update
```

Or click **Check for updates** in the Settings tab.

### Uninstalling

```
uv tool uninstall jobhunt-app
```

Or check the **Settings** tab for the exact command.

---

## What it does

- **17 job board adapters**: Greenhouse, Lever, Ashby, Workable, SmartRecruiters,
  Recruitee, Workday, RemoteOK, HackerNews, SimplifyJobs, Arbeitnow, Jobicy,
  Himalayas, TheMuse, Arbeitsagentur (Germany), Jooble (69 countries), Reed (UK).
- **15 stackable filters**: keyword, company, location, remote/hybrid/onsite,
  level, job type, salary, degree, experience, languages, skills, date,
  visa sponsorship, CV match, and sort order.
- **Salary on every job**: real data where available, plus a self-calibrating estimator.
- **CV match**: upload your CV and sort jobs by how well they fit your experience.
- **Saved searches**: get desktop notifications when new matching jobs appear.
- **Auto-refresh**: re-scrape every N hours in the background.
- **Add companies**: from the Sources tab — no config files needed.
- **Settings page**: update, clear data, uninstall — all from the UI.

## How it works

Companies use applicant-tracking systems (Greenhouse, Lever, Ashby, etc.)
with stable public APIs. jobhunt reads from those APIs, stores everything
locally, and gives you a search UI with filters and a CV matcher.

It does **not** scrape LinkedIn or Indeed.

## Privacy

- Everything runs on your machine. Nothing is uploaded.
- No telemetry, analytics, or update pings.
- The UI only listens on `127.0.0.1` (your machine, not your network).
- Your data is at: `~/.local/share/jobhunt/` (Linux), `~/Library/Application Support/jobhunt/` (Mac), `%APPDATA%\jobhunt\` (Windows). Run `jobhunt info` to check.

## Commands

```bash
jobhunt                  # start + open browser
jobhunt --schedule 360   # auto-refresh every 6 hours
jobhunt update           # update to latest
jobhunt doctor           # check which sources work
jobhunt match-cv my.pdf  # score jobs against your CV
jobhunt info             # show file paths
```

## For developers

```bash
git clone https://github.com/Abdalla2004-collab/Jobhunt && cd Jobhunt
uv venv && source .venv/bin/activate
uv pip install -e ".[dev]"
pytest -q      # 69 unit tests
jobhunt        # run locally
```

See [`CONTRIBUTING.md`](CONTRIBUTING.md) for the full guide.

## License

MIT — see [`LICENSE`](LICENSE).
