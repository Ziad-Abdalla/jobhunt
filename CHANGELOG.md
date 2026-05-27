# Changelog

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
