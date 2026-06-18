# jobhunt — resume handoff

**"Continue where we left off" should be enough from this file.**

## Where we are (2026-05-30, HEAD 5a43d68 on `main`)
jobhunt is an already-public MIT PyPI app (`jobhunt-app`, CLI `jobhunt`); FastAPI+Jinja+HTMX+SQLite.
Bug-bounty code already removed (v0.12.0). This session was **planning, not coding**: produced the
full design + executable plan set for the multi-country enhancement, and finished the public-clean cleanup.

- Repo separate from the bug-bounty repo (`Ziad-Abdalla/BountyHunter`) — never confuse them.
- Remote: `github.com/Abdalla2004-collab/Jobhunt`. NOT pushed this session (commits are local; push when asked).
- Baseline: **`pytest -q` = 133 passed**, 11 e2e deselected. `.env` gitignored (Jooble key), no tracked secrets.

## Locked product decisions (owner-approved)
Local-first app + $0 GitHub community layer · hybrid zero-config+pluggable keys (graceful dead-key disable) ·
ONE app, country = menu (UK/DE/QA/MY/US) · maximize legal coverage esp. local non-tech no-experience ·
distance search · free advisory auto-update. Honest gap: QA/MY coverage is thin (Careerjet+JSearch only).

## The plan set (READ IN THIS ORDER to execute)
1. `docs/superpowers/plans/2026-05-30-jobhunt-MASTER-roadmap-and-contracts.md` — **read FIRST**. Locked
   contracts C1–C10 + ownership ledger + semantic locks (resolves all cross-batch ambiguity).
2. The 7 batch plans `…-B1..B7-*.md` (each TDD red→green→commit, 6–14 tasks, ends green).
3. `docs/superpowers/specs/2026-05-30-jobhunt-enhancement-design.md` (design) and
   `docs/internal/research/JOBHUNT_ENHANCEMENT_2026_05_30/00-SYNTHESIS-AND-RECOMMENDATIONS.md` (evidence).
4. `docs/INDEX.md` is the knowledge manifest.

## 2026-06-19 — LIVE & USABLE for owner's real search (v0.13.1, pushed, tag v0.13.1)
Owner pasted their Reed key -> Track 2 UNLOCKED. Now: 32k active jobs, ~275 no-exp local near London (1,430 entry-level), 368 London software. Shipped this session: Reed near-me distance scoping; **entry-level default for local roles** (was mislabelled 'mid' -> 0-exp filter now works, +1,400 entry); **non-blocking refresh** (/api/refresh returns 0.12s + /api/refresh/status polling, app.js polls); concurrency 4->8 + Reed depth 500->300 (faster); **stale window 14->30 days**; Multiverse apprenticeships. 141 tests green. Reed key lives ONLY in gitignored .env (owner's key: in Settings on their PC). PUSHED main + tag v0.13.1 (PyPI auto-publish unreliable -> owner installs from GitHub tag).
Owner PC install: `uv tool install --reinstall "git+https://github.com/Abdalla2004-collab/Jobhunt.git@v0.13.1"` then Settings: location London + paste Reed key + Jooble key -> Refresh.
Known minor: extract.py level mis-tags titles containing the word 'staff'/'team' as senior (edge case). Reed expirationDate not yet used for sweep (could keep until actual expiry — future).

## 2026-06-18 — app tuned for owner's real use (v0.13.0, HEAD da95440, not pushed)
Owner wants to USE it now: London SWE internships OR loads of part-time 0-exp near Whitechapel, fresh, daily.
Shipped: Reed near-me distance scoping (TDD), London early-career boards, Jooble Kentucky fix, fresh scrape
(27,711 active), 3 alerts, auto-refresh, `.env` set (London/15mi). Track 1 (London software early-career)
WORKS + verified in UI (clean). **Track 2 (local part-time near Whitechapel) is empty pending ONE owner
action: a free Reed key** (reed.co.uk/developers/jobseeker → Settings → Refresh) — that data isn't on any
free no-key feed. Activation guide is in the owner hub manual-steps page. 135 tests green.
**Next: if owner adds the Reed key → verify Local part-time fills; else build B1 (Careerjet adds a free
local/QA/MY source, reducing the single-key dependency).**

## THE LONGER-TERM ROADMAP NEXT ACTION
**Execute Batch B1** = `docs/superpowers/plans/2026-05-30-jobhunt-B1-resilience-and-careerjet.md`
(shared hardened HTTP session + per-source circuit breaker + `SourceHealth` + Careerjet scraper,
which closes the Qatar/Malaysia/non-tech gaps). Read the MASTER doc first, then run B1 task-by-task with
`superpowers:test-driven-development` + `superpowers:subagent-driven-development`. Build **B1→B7 in order**,
one batch to green + docs updated + version bump + commit, then pause for owner "continue".

## Rules that bite (repo CLAUDE.md)
TDD + respx + one fixture/new-scraper · no inline `<script>` AND no inline event handlers (wire in
`static/app.js`) · fixed-dropdown filters · 4 employment types · `?v={{version}}` cache-bust ·
CV upload never fails without ML deps · keep README/CONTRIBUTING/CHANGELOG/CLAUDE.md + this SESSION_LOG
current per batch · external API shapes fetched at BUILD time via context7 (master C10).
