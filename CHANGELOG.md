# Changelog

## [0.9.0] — 2026-05-28

### Added
- **CV upload always works.** Without `sentence-transformers` installed, jobhunt now
  falls back to a keyword-overlap CV match (skills + languages) so uploads no
  longer return `{"detail": "CV matching requires sentence-transformers..."}`.
  Installing the `[match]` extras transparently upgrades to semantic cosine
  similarity. No more terminal commands to "make it work".
- **One-click uninstall.** The Settings page now has an actual **Uninstall jobhunt**
  button — it runs `uv tool uninstall jobhunt-app` / `pipx uninstall …` and shuts
  the server down so the OS releases the files. No more copy-pasting commands.
- **Split Check vs Install for updates.** The old single button mixed
  "check for updates" with "install the upgrade now", and the failure messages
  were opaque. *Check for updates* is now passive (calls `/api/check-update`)
  and surfaces a separate **Install update** button only when a new version is
  available.
- **Local Jobs pivot: zero-experience first.** The `/local` page is now built
  around the everyday entry-level work most people actually need near home —
  cleaning, retail, warehouse, hospitality, care, customer service, driving,
  reception, security. Tech / software is still one click away via the new
  *What kind of work* dropdown.
- **Find a Job (DWP) scraper.** Free UK government job board with strong
  non-tech coverage. 19 default sources cover all major UK cities plus
  category-targeted pulls (cleaning, warehouse, retail, kitchen, delivery,
  reception, customer service, care, security).
- **Tech / non-tech classifier.** Every job is now tagged with a `category`
  (`tech`, `nontech`, or `other`) at scrape time; a one-time migration
  back-classifies existing rows on first boot.
- **Bug bounty reward data — actual numbers, never estimates.** Intigriti,
  YesWeHack, and Bugcrowd payout ranges are now pulled directly from the
  upstream data. HackerOne entries surface `offers_bounties` / `offers_swag`
  plus response-efficiency % and average days-to-resolve. New filters: *Pays
  cash* / *Cash or swag*, plus sort by highest max payout, highest min
  payout, or most responsive.
- **Cache-busted static assets.** `style.css?v={{ version }}` and
  `app.js?v={{ version }}` on every template so browsers stop serving stale
  copies after upgrade.

### Changed
- **Career stage filter no longer duplicates "Internship".** The Jobs page used
  to show "intern" in *Level* AND "Internship" in *Job type*. Career stage is
  now permanent-role seniority only (entry → senior); use *Job type →
  Internship* for the contract type. Adds an explicit hint on both filters.
- **/sources page no longer 500s after an in-place upgrade.** Wrapped the
  YAML loader in a graceful fallback that serves an empty state with an
  inline retry hint instead of crashing the page.
- **CV match modes are visible.** The CV page shows whether you're in
  semantic or keyword mode and how to upgrade if you want the bigger model.

### Fixed
- After clicking the old *Check for updates* button (which actually ran the
  install), subsequent `/sources` and `/api/refresh` requests could 500.
  Splitting check from install + hardening the sources renderer closes both
  symptoms.

## [0.7.2] — 2026-05-28

### Added
- **4 app sections**: Jobs (main search), Local Jobs (UK/Germany entry-level),
  Freelance & Contract, Bug Bounty (HackerOne/Bugcrowd/Intigriti/YesWeHack).
- **Local Jobs page**: 35+ UK/Germany regions (Whitechapel, Stuttgart, Berlin,
  Manchester, etc.). Max-experience filter (0-5 years). 200 results per search.
- **Freelance page**: filters Contract/Freelance jobs with keyword, work mode,
  salary. Sorted by most recently posted.
- **Bug Bounty page**: 871 programs from bounty-targets-data (GitHub). Search
  by company/domain, filter by platform. Auto-refreshes with main refresh.
- **Settings page**: API key fields (Jooble + Reed), user location, check for
  updates button, clear all jobs button, uninstall instructions.
- **Desktop shortcut**: Windows install script creates `jobhunt.bat` on Desktop.
- **Intern-focused sources**: SimplifyJobs internships/new-grad, German
  Praktikum/Werkstudent/Ausbildung/Junior/Trainee, Reed UK junior/graduate.
- **15 UK company boards**: Trustpilot, Wise, Checkout.com, Starling Bank,
  Snyk, Onfido, iwoca, Airwallex, 1Password, Made Tech, Hugging Face, etc.
- **PyPI publishing**: `pip install jobhunt-app` works. Published via uv.

### Changed
- **UI overhaul**: newspaper theme replaced with clean modern blue/white design.
  Dark mode. Mobile responsive. Rounded cards, pill badges.
- **Filters simplified**: Job type, Degree, Visa now clean dropdowns (4 fixed
  options) instead of dynamic radio buttons that showed 30+ raw values.
- **Employment type normalization**: 60+ raw variants (FullTime, berufserfahren,
  Working student, etc.) mapped to 4 canonical types (Full-time, Part-time,
  Contract, Internship). DB migration runs on every startup.
- **Level detection overhauled**: split into title-only and description-only
  patterns. Now catches co-op, ausbildung, azubi, trainee, apprentice,
  associate, "0-1 years". False positives fixed (e.g. "graduate degree" no
  longer triggers entry-level on senior roles).
- **Apply link**: shows "Apply" instead of truncated URL.
- **All JS moved to app.js**: no inline scripts. Fully CSP compliant.
- **Install scripts**: uninstall old versions before installing, create desktop
  shortcut, show version after install.

### Fixed
- CSP blocked inline scripts in settings.html — buttons were dead.
- PowerShell installer crashed: `$ErrorActionPreference='Stop'` treated uv
  stderr as fatal error.
- Old CSS variables (`--moss`, `--font-display`) left in templates after rewrite.
- Missing root `.muted` CSS class — dozens of elements unstyled.
- Dark mode: hardcoded `rgba(0,0,0,0.1)` borders invisible.
- `clear-data` deleted SQLite file breaking engine pool — now truncates tables.
- `jobhunt update` CLI used wrong package name (`jobhunt` instead of `jobhunt-app`).
- `/api/uninstall` returned `jobhunt` instead of `jobhunt-app`.
- Salary parsing: "1.5k" was parsed as 15,000 (dot removed before k-handler).
- Windows notifications: quotes in job titles broke PowerShell command.
- "Senior Associate Engineer" false-positive as entry-level — added negative lookbehind.
- 12+ broken source slugs removed (companies changed ATS platforms).

### Data
- 24,303 jobs from 130+ sources across 17 scrapers.
- 3,329 intern/entry/junior roles detected (13.7%).
- 871 bug bounty programs cached.
- 1,040 London jobs, 1,056 Stuttgart jobs, 2,334 remote jobs.

### Tested
- 69 unit tests, 7 E2E Playwright tests, 25 endpoint checks, 20 edge cases.
- 3 full iteration passes with 6 parallel audit agents.

## [0.1.0] — 2026-05-22

### Added
- Initial release with 9 ATS adapters, editorial UI, CV matching, saved
  searches, desktop alerts, Docker support, CSRF defence, CSP headers.
- 11,388 jobs from 38 sources. 53 tests passing.
