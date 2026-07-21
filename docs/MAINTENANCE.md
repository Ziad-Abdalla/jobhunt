# jobhunt — source maintenance handbook

> Sources rot. APIs expire, RSS feeds change shape, companies move ATS,
> free tiers tighten. This doc + the paired
> `source-maintenance` skill at `.claude/skills/source-maintenance/SKILL.md`
> together are the durable process for keeping jobhunt useful in 6 months,
> 12 months, 24 months — without any single person having to remember the
> whole picture.
>
> **Read this if you're about to** add a job source, remove one, debug
> "no jobs in my country", investigate an API-key error, plan a country
> expansion, or hand the project off to a future contributor.

---

## 0. The defensive/offensive split

This handbook is paired with two automatic mechanisms in the app:

- **Defensive (in-app):** `scrape_all()` auto-skips any source that has
  failed three consecutive scrapes — no human or AI required. The
  Settings page surfaces the count. This stops the bleed.
- **Offensive (paired skill):** the `source-maintenance` skill at
  `.claude/skills/source-maintenance/SKILL.md` researches replacements,
  discovers new free APIs, and adds them.

Run the skill periodically; the app handles routine decay on its own.

---

## 1. Why sources rot (the failure modes we plan for)

| Failure | Symptom | Detection |
|---|---|---|
| **API key expired / revoked** | Jooble or Reed scraper returns 401/403 | `jobhunt doctor` → `FAIL  (Reed UK)  HTTPStatusError: 401` |
| **API rate-limit tightened** | Some calls succeed, others time out | `jobhunt doctor` → mixed `ok` / `warn` for the same source type |
| **Company changed ATS slug** | `greenhouse:foobar` 404s | `jobhunt doctor` → `FAIL` |
| **Company migrated platform** | Old slug returns 404, but they're hiring on Ashby now | `doctor` flags; replacement needs research |
| **RSS endpoint URL changed** | scraper hits 404 / receives HTML in place of XML | `doctor` → `FAIL` on the source |
| **Schema drift** | A source's JSON gains/loses a field; parser silently drops it | `doctor` says ok, but UI shows partial data |
| **Free tier removed** | "This API now requires a paid plan" | `doctor` says ok, but with limited results |
| **New free API appears** | A government opens a public job feed | No detection — we have to actively search |

The skill catches the detectable rows; **schema drift** and **new-API
discovery** are the two it can't. Schema drift needs the spot-check
rituals in §6; new-API discovery is a periodic active search (§7).

---

## 2. The 23 source adapters we ship today

| Source | Auth | Coverage | Strong for | Country bias |
|---|---|---|---|---|
| `greenhouse` | none | Per-company ATS | Tech mid+senior | US/UK |
| `lever` | none | Per-company ATS | Tech mid+senior | US |
| `ashby` | none | Per-company ATS | Tech mid+senior | US/EU |
| `workable` | none | Per-company ATS | Tech, EU | EU |
| `smartrecruiters` | none | Per-company ATS | Tech, EU | EU |
| `recruitee` | none | Per-company ATS | Tech, NL/DE | NL/DE |
| `workday` | none | Per-company ATS | Enterprise tech | Global |
| `remoteok` | none | Aggregator | Remote tech | Global |
| `hackernews` | none | "Who is hiring" thread | Tech startups | US |
| `simplifyjobs` | none | Internships + new-grad | Intern + entry tech | US |
| `arbeitnow` | none | Aggregator | Tech, EU | DE |
| `jobicy` | none | Remote aggregator | Remote tech | Global |
| `himalayas` | none | Remote aggregator | Remote tech | Global |
| `themuse` | none | Aggregator | Tech mid | US |
| `arbeitsagentur` | none | German Federal Employment Agency — all sectors | Praktikum, Ausbildung, Werkstudent, non-tech | DE |
| `jooble` | **key** | 69-country aggregator | Generalist | Global (with key) |
| `reed` | **key** | UK's largest job board — all sectors, incl. non-tech | All sectors, UK | UK |
| `wuzzuf` | none | Largest Egypt job board — all sectors, RSS firehose | All sectors, entry→senior | **Egypt** |
| `remotive` | none | Curated remote aggregator (JSON) | Remote tech | Global |
| `workingnomads` | none | Remote aggregator (JSON) | Remote tech | Global |
| `weworkremotely` | none | Per-category remote RSS | Remote tech | Global |
| `pythonjobs` | none | python.org job board RSS | Python roles | Global |
| `jsearch` | **key** | JSearch/RapidAPI — Google-for-Jobs aggregation | Egypt/MENA + remote (indirect) | **Egypt/MENA** (with key) |

> 🗒️ 2026-07 expansion (17 → 23 adapters): first `wuzzuf` + 4 remote sources
> (all free, no-auth, live-verified) closed the Egypt/MENA + worldwide-remote
> gaps; later `jsearch` (P8, BYO-key RapidAPI, indirect Egypt/MENA + remote,
> off by default) was added. See `docs/internal/EXPANSION_PLAN_2026_07_20.md`.

> 🗒️ `findajob` (UK DWP) was removed in v0.9.1 — DWP deprecated their
> `?format=rss` query and every URL now returns HTML. UK non-tech
> coverage moved to Reed broader keywords. See audit log §10.

**Key takeaways for adding coverage:**
- For a new country, look for a **government-run** job feed first (free,
  stable, all-sector). Examples we haven't yet integrated: USAJobs (US
  federal), Indeed Sponsored Jobs API (US, free tier), France's Pôle
  Emploi (FR), Spain's SEPE (ES), Australia's JobSearch (AU).
- For tech-specific country coverage, look for **company ATS aggregators**
  with a public free tier (Greenhouse + Lever cover most US tech; ATS in
  $country is the question to ask).
- Free RSS/Atom feeds are second-best — stable but lossy.

---

## 3. Quick health check

```bash
jobhunt doctor                # human-readable
jobhunt doctor --json         # machine-readable for the skill
```

What it shows:
- `ok    Company  N jobs` — scraper ran, returned data.
- `WARN  Company  0 jobs returned` — scraper ran but found nothing. Could
  be legitimate (e.g. they're not hiring), could be a quiet break.
- `FAIL  Company  HTTPStatusError: 404` — broken. Needs action.

Run this before every release. If anything is `FAIL`, fix or remove
before publishing — users notice missing data faster than missing
features.

---

## 4. The repair decision tree

When `doctor` reports a `FAIL` on `<source>/<board>` (company `<X>`):

```
Did the URL the scraper hit return 404, or did the API key get rejected?

├── 404 / "not found"
│    │
│    ├── Is the company still hiring? (visit their /careers page)
│    │    │
│    │    ├── Yes, but they migrated ATS
│    │    │      → Update sources.yaml: change `source:` to new platform,
│    │    │        update `board:` to the new slug.
│    │    │        Example: { source: lever, board: stripe } →
│    │    │                 { source: ashby, board: stripe }
│    │    │
│    │    └── Yes, same ATS, but new slug
│    │           → Just update `board:`.
│    │
│    └── No, or unreachable
│           → Remove from sources.yaml entirely.
│             Log the removal in §10.
│
├── 401 / 403 — API key auth fails
│    │
│    ├── Is the key set in the user's .env?  (jobhunt -> /settings)
│    │    No → Tell the user via the Sources page error message.
│    │
│    ├── Did the provider deprecate the auth method?
│    │    Yes → Update the scraper class (src/jobhunt/scrapers/<provider>.py).
│    │           Bump the package minor version.
│    │
│    └── Otherwise key is invalid → the user must regenerate it.
│
├── 429 — rate limited
│    │
│    └── Lower `_MAX_JOBS` in the scraper, or cache more aggressively,
│         or back off with retries. See src/jobhunt/scrapers/<source>.py.
│
└── Other (timeout, DNS, TLS error)
     │
     └── Sometimes transient. Re-run `doctor` after a minute. If it
         keeps failing for 2+ checks, treat as broken.
```

---

## 5. Adding a new free source

The cheapest add is when the new source matches an existing scraper class
(e.g. another Greenhouse-using company). The expensive add is a new
scraper class (a new ATS / new public RSS shape).

### 5a. New entry for an existing scraper

1. Append to `src/jobhunt/sources.yaml` near similar entries:
   ```yaml
   - { source: greenhouse, board: acme,  company: "Acme Corp" }
   ```
2. Run `jobhunt doctor` to verify it returns jobs.
3. Run `jobhunt scrape` (or click Refresh in the UI) to populate the DB.
4. Verify the jobs flow through filters:
   - Open the Jobs page, search for the company. Real entries should show.
   - Check that `level`, `employment_type`, `remote`, `salary` populated.
5. If a job in the new source has unusual employment-type text, add the
   variant to `_EMPLOYMENT_TYPE_MAP` in `src/jobhunt/refresh.py`.
6. Log the addition in §10.

### 5b. New scraper class (new source type)

1. Create `src/jobhunt/scrapers/<name>.py` subclassing `BaseScraper`.
   Implement `async def fetch()` yielding `RawJob` instances. Look at
   `arbeitnow.py` (no-key) or `reed.py` (with API key) as a model.
2. Register in `src/jobhunt/scrapers/__init__.py` `SCRAPER_REGISTRY`.
3. Add a unit test in `tests/test_<name>.py` with a `respx` mock.
4. Add default entries to `src/jobhunt/sources.yaml`.
5. Run `pytest -q` and `jobhunt doctor`.
6. Bump the version with `./scripts/release.sh <new-version>`.

### 5c. Where to look for free, stable APIs

| Region | Candidate |
|---|---|
| UK | Civil Service Jobs (gov.uk), NHS Jobs RSS, Reed (✅ broad coverage) |
| Germany | Arbeitsagentur (✅ done), StepStone (only via partner) |
| US | USAJobs.gov (free with key), GitHub's "who is hiring" thread |
| France | Pôle Emploi "Offres d'emploi" API (free with key) |
| Spain | SEPE Trabaja, Infojobs (commercial only) |
| Australia | JobSearch.gov.au, careers.act.gov.au |
| Canada | Job Bank (jobbank.gc.ca) public RSS |
| Netherlands | UWV Werk.nl (public job board) |
| Ireland | Jobs Ireland (gov.ie) |
| Singapore | MyCareersFuture (free with key) |
| India | Naukri (commercial), Internshala (partner-only) |
| Brazil | Catho (commercial), SINE public |
| Egypt | Wuzzuf (commercial), gov.eg portals |
| Generic | Jooble (✅ done — 69 countries with one key), GitHub `awesome-job-boards` |

**Trust hierarchy for picking:**
1. Government feed (usually most stable; rare schema changes).
2. Major aggregator with documented public API.
3. ATS-based per-company endpoints (Greenhouse/Lever pattern).
4. RSS feeds (stable but lossy).
5. HTML scraping (last resort; brittle, prone to breaking weekly).

We do **not** scrape LinkedIn or Indeed — both prohibit it in their ToS.

---

## 6. Schema-drift spot check

Schema drift (a field upstream silently changes shape) is the failure
mode `doctor` cannot catch. Periodic spot check, ideally once a quarter:

1. Open `/local?location=London`. Confirm a mix of categories show; if
   the *No-experience local work* count is suspiciously low, the Find a
   Job RSS may have lost the `<description>` content we rely on.
2. Open `/`. Search for a known company. Confirm salary badges appear
   on most rows.
3. Run `jobhunt scrape --once` (if implemented) or click Refresh — note
   the `added/seen/removed` numbers. A scrape that returns near-zero
   for previously-rich sources signals drift.

If a check fails, file an audit entry (§10) and run the
`source-maintenance` skill to diagnose.

---

## 7. Periodic active search (every ~6 months)

**New in P7 (2026-07):** `jobhunt discover-boards` automates the "harvest new
ATS board slugs" half. It fetches public GitHub company directories
(remoteintech/remote-jobs, awesome-remote-job), extracts Greenhouse/Lever/
Ashby/Workable/SmartRecruiters/Recruitee slugs, dedupes against the current
`sources.yaml`, and writes UNVERIFIED candidates to
`data/discovered_boards.yaml`. It NEVER edits `sources.yaml` — run
`jobhunt doctor` against the merged entries and drop any 404s before shipping
(the verify-before-ship rule). Known limitation: directories that link to
per-company profile files (rather than embedding ATS URLs) are under-harvested.

The skill does the heavy lifting, but a human eye every six months
catches things the skill won't:
- New free APIs we don't know to search for.
- Existing free tiers tightening.
- Whole categories of work the app isn't yet serving.

Cadence: every January and July, ask Claude to run the
`source-maintenance` skill with the `--discover` flag (see SKILL.md). It
will surface candidate additions for review.

---

## 8. Trust + freshness contract per source

For every source entry we ship, the implicit contract is:

> This entry returned jobs the last time we checked. We will re-check it
> on every release (`scripts/release.sh` runs `jobhunt doctor` if you
> add it to the pre-flight). If it fails on two consecutive checks
> separated by at least a week, we remove it.

The audit log (§10) records every add + every remove + the date.

---

## 9. Wiring the skill into normal sessions

The skill at `.claude/skills/source-maintenance/SKILL.md` triggers when
the user says any of:
- "check our sources"
- "source maintenance"
- "what's broken"
- "find new APIs"
- "country expansion"
- "anything fail in doctor"
- "republish jobhunt" (rolls health-check + replacement-research in)

Use it freely — the cost of running it is a few minutes of Claude time
and a handful of `jobhunt doctor` calls. The win is that the project
survives without you having to remember the whole maintenance picture.

---

## 10. Audit log (chronological)

> Append at the bottom — never reorder. One line per event. Format:
> `YYYY-MM-DD  <action>  <source>/<board>  — <reason> — <by>`

```
2026-05-28  add     findajob/<19 entries>                          — UK gov, no key, non-tech                                 — initial v0.9.0 ship
2026-05-28  remove  findajob/<all 19 entries>                      — DWP deprecated ?format=rss; every URL now returns HTML   — source-maintenance skill, iteration 1
2026-05-28  remove  scraper class findajob.py                      — no working replacement endpoint; new DWP REST API is partner-only — source-maintenance skill
2026-05-28  add     reed/cleaner                                   — Reed UK non-tech, replaces findajob/cleaner              — source-maintenance skill
2026-05-28  add     reed/warehouse                                 — Reed UK non-tech, replaces findajob/warehouse            — source-maintenance skill
2026-05-28  add     reed/retail assistant                          — Reed UK non-tech, replaces findajob/retail               — source-maintenance skill
2026-05-28  add     reed/kitchen porter                            — Reed UK non-tech, replaces findajob/kitchen              — source-maintenance skill
2026-05-28  add     reed/delivery driver                           — Reed UK non-tech, replaces findajob/delivery             — source-maintenance skill
2026-05-28  add     reed/receptionist                              — Reed UK non-tech, replaces findajob/reception            — source-maintenance skill
2026-05-28  add     reed/customer service                          — Reed UK non-tech, replaces findajob/customer service     — source-maintenance skill
2026-05-28  add     reed/care assistant                            — Reed UK non-tech, replaces findajob/care                 — source-maintenance skill
2026-05-28  add     reed/security officer                          — Reed UK non-tech, replaces findajob/security             — source-maintenance skill
2026-05-28  fix     scraper arbeitnow.py                            — handle 403 / 429 mid-pagination as end-of-feed not error — source-maintenance skill
2026-05-28  add     arbeitsagentur/Reinigungskraft                  — DE non-tech parity with UK Reed Cleaning                  — v0.10.2
2026-05-28  add     arbeitsagentur/Lagerarbeiter                    — DE non-tech parity with UK Reed Warehouse                 — v0.10.2
2026-05-28  add     arbeitsagentur/Verkäufer Einzelhandel           — DE non-tech parity with UK Reed Retail                    — v0.10.2
2026-05-28  add     arbeitsagentur/Küchenhilfe                      — DE non-tech parity with UK Reed Kitchen                   — v0.10.2
2026-05-28  add     arbeitsagentur/Lieferfahrer                     — DE non-tech parity with UK Reed Delivery                  — v0.10.2
2026-05-28  add     arbeitsagentur/Empfangskraft                    — DE non-tech parity with UK Reed Reception                 — v0.10.2
2026-05-28  add     arbeitsagentur/Kundenservice                    — DE non-tech parity with UK Reed Customer Service          — v0.10.2
2026-05-28  add     arbeitsagentur/Pflegehelfer                     — DE non-tech parity with UK Reed Care                      — v0.10.2
2026-05-28  add     arbeitsagentur/Sicherheitsmitarbeiter           — DE non-tech parity with UK Reed Security                  — v0.10.2
2026-07-20  add     greenhouse/tamara                              — MENA (Saudi) fintech; live-verified 39 jobs              — P7 expansion
2026-07-20  add     greenhouse/careem                              — MENA (UAE/Egypt) super-app; live-verified 28 jobs        — P7 expansion
2026-07-20  remove  greenhouse/unity3d                             — 404; Unity left public greenhouse, no findable ATS slug  — doctor pass (170 sources: 130 ok, 39 warn, 1 error)
2026-07-21  fix     scraper jsearch.py                             — upstream retired /search → migrated to /search-v2 (data.jobs wrapper, country param, work_from_home, enum job_employment_types); added per-second throttle + 429 retry — P8 live probe with owner key
2026-07-21  verify  jsearch/<4 owner boards>                       — live-verified 39 jobs, 34 real employers (Siemens, Orange, Toptal, almentor…), Egypt + remote — P8 live probe
```

When the skill runs, it appends its findings here as `verify` /
`replace` / `remove` lines:

```
YYYY-MM-DD  verify  greenhouse/acme                                — 47 jobs returned, ok                                      — Claude
YYYY-MM-DD  remove  lever/oldcorp                                  — 404 for 14 days; site retired                            — Claude
YYYY-MM-DD  replace lever/foo → ashby/foo                          — Foo migrated ATS; new slug verified, 23 jobs              — Claude
YYYY-MM-DD  add     greenhouse/newcompany                          — discovered via /awesome-job-boards search                 — Claude
```
