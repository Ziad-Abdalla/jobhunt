---
name: source-maintenance
description: |
  Long-term maintenance hand for jobhunt's data sources. Use this when the
  user asks any of: "check our sources", "source maintenance", "what's
  broken in jobhunt", "find new APIs", "country expansion", "anything fail
  in doctor", "republish jobhunt", "is jobhunt still pulling data", or any
  question that implies the data layer needs attention. Pair this skill
  with the human doc at docs/MAINTENANCE.md — the doc is the rulebook,
  this skill is the hand that follows it.

  Triggers (the user says/asks):
    • "run source maintenance" / "/source-maintenance"
    • "check what's broken"
    • "find more free APIs"
    • "any sources down?"
    • "country X has nothing — fix it"
    • "audit our data layer"
    • "schema drift check"
    • "before we release, check sources"

  Skip when:
    • The work is purely UI / template / styling (no data layer).
    • The user is debugging a single specific scraper — use the debugger.

metadata:
  type: maintenance
  shared: true   # in-repo, applies to every contributor's Claude session
  cadence: per-release + every ~6 months for discovery
---

# source-maintenance — keeping jobhunt's data layer alive

## What this skill is for

jobhunt depends on ~150 external data points (per-company ATS endpoints,
public RSS feeds, GitHub-hosted datasets, paid-with-free-tier APIs).
**These will rot.** API keys expire, companies migrate ATS, gov endpoints
get redesigned, free tiers tighten, bounty repos relocate, new countries
open public job feeds we don't yet read.

Without active maintenance, the app degrades into "no jobs in my country"
within months. With this skill, the maintenance discipline is captured as
a repeatable workflow that any contributor (human or future-Claude) can
execute in 10–30 minutes per release.

This skill is **shared across every contributor's Claude session** —
because it lives at `.claude/skills/source-maintenance/SKILL.md` inside
the repo, every Claude that operates in this checkout picks it up
automatically. No setup needed beyond pulling main.

## Required reading before this skill runs

Open these in order:
1. `docs/MAINTENANCE.md` — the rulebook. Repair decision tree, free-API
   trust hierarchy, audit-log convention.
2. `src/jobhunt/sources.yaml` — the current source set.
3. `src/jobhunt/scrapers/__init__.py` — the SCRAPER_REGISTRY (what
   source types we can wire to).
4. The last entry in `docs/internal/SESSION_LOG.md` — context for the
   current session.

## The workflow — five phases

### Phase A. Detect — what's the state of the world right now

```bash
jobhunt doctor --json > /tmp/jobhunt-doctor.json
```

Parse the JSON. Buckets:
- `ok` rows — leave alone.
- `warn` rows (0 jobs returned) — may be legitimate (slow hiring week)
  or quiet break. Cross-check the last successful scrape in
  `data/jobhunt.db` `scrape_runs` table.
- `error` rows — definitely broken. Capture `source`, `board`, `company`,
  `detail`.

If everything is `ok`, jump to Phase D — there's still discovery work.

### Phase B. Diagnose — for each broken source, decide the action

For each error row, walk the **repair decision tree** in
`docs/MAINTENANCE.md` §4. Cases:

- **404 from the scraper** → curl the URL the scraper hits. If the page
  redirects to a different ATS, the company migrated. Update
  sources.yaml accordingly. If it's gone entirely, remove the entry.
- **401 / 403** → API key issue. Don't auto-fix — tell the user via the
  audit log and the in-app Sources page error.
- **429** → rate-limited. Lower `_MAX_JOBS` in the scraper file or
  back-off; do not just delete.
- **Connection / DNS / TLS error** → transient. Re-run doctor twice
  more, 60s apart. Only act if it fails 3× in a row.

Output of Phase B: a concrete edit list (yaml entries to remove,
replace, or annotate).

### Phase C. Research — find replacements for removed/dead entries

Two flavours of research:

**C1. Same-company replacement.** Company X used to be on Lever. Visit
their /careers page (WebFetch). Identify the new ATS by URL pattern:
- `boards.greenhouse.io/<slug>` → greenhouse
- `jobs.lever.co/<slug>` → lever
- `jobs.ashbyhq.com/<slug>` → ashby
- `apply.workable.com/<slug>` → workable
- `careers.smartrecruiters.com/<slug>` → smartrecruiters
- `<slug>.recruitee.com/o/` → recruitee
- `*.myworkdayjobs.com/<slug>` → workday

Update sources.yaml with the new `{source, board, company}` triple.

**C2. New free APIs we don't yet have.** Walk the country/category
matrix in MAINTENANCE.md §5c. For each underserved country (we currently
only auto-cover UK + Germany strongly), search the web for:

- `"<country> public job board API"`
- `"<country> government jobs RSS"`
- `"<country> free jobs API no key"`
- `"<country> ATS aggregator"`

Trust hierarchy (from MAINTENANCE.md §5c):
1. Government feed
2. Major aggregator with documented free API
3. ATS-based per-company endpoints
4. RSS feeds
5. HTML scraping — last resort, brittle. We do **not** scrape LinkedIn
   or Indeed (their ToS prohibits it).

For each candidate, verify the endpoint actually returns data with a
single curl/WebFetch, and confirm a free tier exists.

### Phase D. Apply — write the changes

1. **Edit `src/jobhunt/sources.yaml`**. Group new entries near similar
   ones. Use the comment-block style already in the file.
2. **If a new scraper class is needed** (the new source doesn't match
   any in SCRAPER_REGISTRY), create `src/jobhunt/scrapers/<name>.py`
   following the `findajob.py` template (no-key) or `reed.py`
   (key-required). Register in `src/jobhunt/scrapers/__init__.py`.
3. Run `jobhunt doctor` again. Every new entry must be `ok` before
   moving on. If a candidate is `warn` (0 jobs), keep it but flag in
   the audit log — it may be a slow-hiring board.
4. Trigger a partial scrape:
   ```bash
   jobhunt scrape  # or call /api/refresh
   ```
   Wait for it to finish. Count how many new jobs landed:
   ```bash
   sqlite3 data/jobhunt.db "SELECT source, COUNT(*) FROM jobs GROUP BY source ORDER BY 2 DESC;"
   ```
5. **Filter-mapping check** — confirm the new data plays with existing
   filters:
   ```bash
   .venv/bin/python -c "
   from fastapi.testclient import TestClient
   from jobhunt.main import app
   with TestClient(app) as c:
       # Pick something from the new source
       r = c.get('/api/jobs', params={'company': '<new-co>'})
       print('total:', r.json()['total'])
       r = c.get('/api/jobs', params={'level': 'entry'})
       print('entry-level total:', r.json()['total'])
       r = c.get('/local', params={'location': '<relevant city>', 'category': 'any'})
       print('local status:', r.status_code)
   "
   ```
   Confirm:
   - Jobs from the new source have `category` populated correctly
     (`classify_category` recognises their titles).
   - `employment_type` normalised to one of the 4 canonical values
     (see `_EMPLOYMENT_TYPE_MAP` in `refresh.py`).
   - Salary appears when upstream provided it.
   - The location is searchable via the /local route's regional map.
6. If any of the above fails, extend the mapping:
   - Title patterns not classified → add to
     `_TECH_TITLE_RE` / `_NONTECH_TITLE_RE` in `extract.py`.
   - Employment-type variants → add to `_EMPLOYMENT_TYPE_MAP` in
     `refresh.py`.
   - Unknown city not in regional map → add to `_REGION_MAP` in
     `main.py`.

### Phase E. Record + ship

1. **Append entries to `docs/MAINTENANCE.md` §10** for every action.
   Format: `YYYY-MM-DD  add|verify|replace|remove  source/board  — reason  — Claude (skill)`.
2. **Update CHANGELOG.md** under the new minor version. Reference the
   audit-log entries.
3. **Update CLAUDE.md** if a new scraper class was added (the
   architecture section lists them).
4. **Run the test suite** — anything regress?
   ```bash
   .venv/bin/python -m pytest -q
   .venv/bin/python -m pytest -m e2e -q
   ```
5. **Release**:
   ```bash
   ./scripts/release.sh <new-minor-version>
   ```
   The script asks "proceed?", then pushes the tag. The GitHub Action
   takes over from there — wheel build, verification, PyPI upload,
   GitHub release. The user gets the new sources via the in-app *Check
   for updates* button or the next install-script re-run.

## Discovery cadence

- **Every release**: run Phase A + B (detect + diagnose) before pushing
  the tag. The release script can call `jobhunt doctor` as a pre-flight
  gate if added.
- **Every ~6 months** (Jan + Jul recommended): run the full A→E. The
  discovery phase tends to surface 2–5 net-new sources each pass.

## Don'ts

- ❌ Never add a source that requires HTML scraping LinkedIn or Indeed.
  Both prohibit it in their ToS.
- ❌ Never silently remove a source without a MAINTENANCE.md audit-log
  entry. The audit trail is the only durable record.
- ❌ Never add a source without verifying it returns data first. A "0
  jobs" entry adds load to every scrape pass for no gain.
- ❌ Don't bump the version unless something actually changed in
  sources.yaml or a scraper. Empty releases are noise.

## Output template

End every run with a summary the user can paste into a commit/PR body:

```
Source maintenance pass — YYYY-MM-DD

Detected:
- <N> ok, <N> warn, <N> error  (from `jobhunt doctor --json`)

Removed:
- <source>/<board>  — <reason>

Replaced:
- <old> → <new>  — <reason>; <N> jobs after fix

Added:
- <source>/<board>  — <country> <category>; <N> jobs returned

Filter-mapping checks:
- <new source> categories: ✓ tech / ✓ nontech / etc.
- employment_type normalisation: ✓
- salary parsing: ✓
- /local regional map: ✓

Audit log: appended <N> entries to docs/MAINTENANCE.md.
CHANGELOG: <new version>.
Release: ./scripts/release.sh <new version>.
```
