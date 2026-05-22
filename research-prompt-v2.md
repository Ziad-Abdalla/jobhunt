# Research brief: JobHunt adapter build queue and access patterns

## Goal
Produce a ranked, ship-ready build queue for JobHunt adapters and the access pattern each adapter must implement. The deliverable is a decision artifact the maintainer can act on within a working day, not an encyclopedia.

Two questions to answer:
1. What are the next 8 adapters to build, in order, and as what tier (API / RSS / ATS / polite HTML / skip)?
2. For each, what is the concrete access pattern, including the ban-signal taxonomy the adapter must implement?

## Operating constraints
- JobHunt is local-first; each user runs their own instance against their own network. No central server.
- Per-user volume: hundreds of listings/day. Adapter must behave correctly behind residential NAT, university NAT, mobile carrier NAT, and commercial VPN exit nodes (pre-burned — assume no rate is safe from them).
- Maintainer capacity: solo, ~1 adapter every 2 weeks, ~6 adapters this quarter. Top-8 list = first 8 build-queue slots, not aspirational.
- Maintainer in Egypt; Egyptian Computer Crimes Law No. 175/2018 governs personal legal exposure.
- Posture: polite consumer of public data. Evasion is an explicit non-goal. See Non-goals at end.

## Required prior-art survey (do this first)
Before any independent research, read and extract from these six exemplars. Each has already answered questions v1 was asking you to derive from scratch:

1. **PaulMcInnis/JobFunnel** — archived Dec 2025 with explicit unwinnable-arms-race post-mortem. Single most important document in this space.
2. **speedyapply/JobSpy** — issues #129 and #302; what happens when 429 is fatal and adapter breakage goes undocumented.
3. **adgramigna/job-board-scraper** — ATS-layer pattern (Greenhouse `boards-api.greenhouse.io`, Lever, Ashby).
4. **RemoteOK Public API** — attribution-as-access business model.
5. **Jobicy** — API + RSS dual-channel with explicit fair-use and named-prohibited redistribution.
6. **JobApis** — historical record of dead APIs (Dice 2017, SimplyHired 2016, Indeed Publisher 2023).

Output: 1-paragraph extraction per exemplar — what they did, what broke, what the maintainer should copy or avoid.

## Part 1 — Site selection (ranked top 8)

Candidates to evaluate (ordered by prior expectation, not final ranking):

- **ATS-layer (structurally distinct — jobs published publicly by product design):** Greenhouse, Lever, Ashby, Workday, Rippling
- **Aggregator-layer with open API + clear fair use:** RemoteOK, Jobicy, Adzuna, The Muse, Arbeitnow
- **Engineer-signal communities:** Hacker News "Who's Hiring", YC Work at a Startup, Wellfound
- **Remote-first boards:** We Work Remotely, Otta / Welcome to the Jungle
- **MENA (maintainer region):** Wuzzuf, Forasna (Egypt), Bayt (pan-MENA), Naukrigulf (GCC)
- **General (interrogate — likely lower-tier):** LinkedIn, Indeed, Glassdoor, ZipRecruiter

**Explicitly cut from consideration:** Monster (zombie post-2020), StackOverflow Jobs (shut 2022), GitHub Jobs (shut 2021).

For each candidate, capture only what feeds the decision:

| Field | Why it's in the brief |
|---|---|
| Listing inventory (from XML sitemap or API `X-Total-Count`) | Primary inventory measure. Binary threshold: ≥10k = sufficient, <10k = thin. |
| Engineering-role share (estimate from sample of 200 listings) | Maintainer's target audience. |
| Remote-role share | Audience weighting. |
| MENA share (if global) or MENA-primary flag | Maintainer's regional weighting. |
| Aggregator-vs-primary | Deprioritize if >60% overlap with already-integrated primary. |
| Business model on access (free / attribution-required / paid / closed) | Determines adapter tier. |
| Deprecation risk | Avoid building on channels likely to close. |

**Explicitly NOT in the brief:** SimilarWeb traffic (job-board numbers are SEO-traffic inflated, not inventory — use only as tiebreaker sanity check); ghost-job rate.

**Ranking formula (apply explicitly, show weights):**
- Engineering-role volume × 3
- Remote share × 2
- MENA share × 2
- Access-channel quality (API > RSS > ATS public > HTML) × 3
- Aggregator overlap discount × −2
- Deprecation risk discount × −2

Output: ranked top-8 table only. No prose preamble.

## Part 2 — Per-adapter access pattern (top 8 only)

Fixed-shape card ≤ 350 words per adapter:

1. **Tier:** A (API) / A-ATS / B-RSS / C (polite HTML) / D (skip)
2. **Endpoint:** URL pattern, auth requirement, attribution requirement (verbatim from ToS)
3. **Rate posture:** Conservative rate from site's published guidance (ToS, robots.txt `Crawl-delay`, API docs). If no published guidance, default floor: **≤6 req/min**. **Do not derive rates from testing-until-blocked.**
4. **Caching:** ETag/If-Modified-Since support? Listing-ID dedup field? Recommended raw-response cache duration.
5. **One known gotcha** (from prior-art or current docs).
6. **Verdict:** Build now / build later / skip, with one-line rationale.

## Part 3 — Cross-site access rules (≤10 bullets, applies to every adapter)

1. Honest fixed User-Agent: `JobHunt/<version> (+https://github.com/<repo>)`. Never rotate, never spoof browser UAs.
2. Library-default Accept / Accept-Encoding headers. No Accept-Language tuning. No HTTP/2 SETTINGS tuning. No TLS fingerprint manipulation.
3. Exponential backoff on 429/503. Respect `Retry-After` exactly when present.
4. **Pre-session health check:** lightweight probe of a known-stable endpoint before committing a full scrape session. Abort early on bad signal.
5. **Silent-zero detection:** every adapter has a known-stable test listing; if expected fields are missing, raise "adapter broken," not "no results."
6. **Circuit-breaker open = adapter disabled.** Not retry-from-different-IP, not UA rotation, not retry-with-cookie. Disable, surface to user, log to maintainer issue tracker.
7. No accounts, no session cookies, no OAuth tokens. **Exception:** official API keys from published developer programs.
8. No headless browser automation of any kind. No timing jitter designed to mimic human cadence (distinct from exponential backoff, which is fine).
9. Residential users apply ~0.3–0.5× of any datacenter-safe rate to account for NAT aggregation. Commercial VPN exit nodes: assume pre-burned, no rate safe.
10. If site bot-detection has fired, the correct response is to stop, not to route around. Any recommendation that helps the tool continue fetching after a detection event is evasion, full stop.

## Part 4 — Ban-signal taxonomy (load-bearing — every adapter must implement)

| Signal | Meaning | Adapter action |
|---|---|---|
| `429` + `Retry-After` | Polite throttle | Back off exactly `Retry-After`, resume at reduced rate |
| `429` no `Retry-After` | Likely shared-NAT aggregation | Longer backoff, surface user warning |
| `403` clears with UA variation | UA-level global block | Disable adapter globally, open maintainer issue (maintainer-side diagnostic only) |
| `403` persistent across UA | IP/ASN block, this user only | User-specific error, suggest different network |
| `2xx` with CAPTCHA challenge body | Soft block | Surface to user, no silent retry |
| `2xx` with login redirect | Auth wall introduced | Architectural change, disable adapter, rework |
| Field-shape mismatch on stable test listing | Site changed HTML silently | "Adapter broken," not "no results" |

## Part 5 — Legal posture (≤200 words, one paragraph)

Single question to answer with citation: **Does any 2024–2026 ruling or statute meaningfully constrain a local-first, user-initiated, unauthenticated public-data fetcher operating from Egypt against US/EU/MENA sites?**

If no, state that and stop. If yes, name the specific constraint and the adapter implication.

Required scan: hiQ v. LinkedIn (post-remand), Meta v. Bright Data, Van Buren, EU DSA Art. 40, Egypt Computer Crimes Law No. 175/2018, UAE Federal Law No. 5/2012 (amended 2021). GDPR scope: software-publisher (not processor) obligations only — one sentence, since local-first tool has near-zero server-side personal-data surface.

## Part 6 — Architecture output (single table — this is the artifact)

| Rank | Site | Tier | Adapter type | Effort signal | Blocker risk | Deprecation risk | Build order |

10 rows max. Lead the deliverable with this table. Everything else is appendix.

## Devil's Advocate section (required, not optional)

Steelman and either accept, reject with citation, or escalate to maintainer:

1. **"Official APIs are a graveyard for indie tools."** LinkedIn partner closed, Indeed Publisher shut 2023, Glassdoor paywalled, Dice/SimplyHired killed. Is Tier A actually populated, or aspirational?
2. **"RSS is 24–72h stale on most boards."** For a job-hunt tool, does staleness make Tier B effectively useless vs polite HTML?
3. **"Local-run posture is legally untested."** hiQ addressed centralized scrapers. Is "each user runs their own instance" a real legal distinction, or rationalization?
4. **"The listed sites are the wrong universe."** Should ATS-layer (Greenhouse/Lever/Ashby/Workday) and aggregator APIs (Adzuna, JSearch, The Muse) displace LinkedIn/Indeed/Glassdoor from the top 8?

Base rates to report:
- API survival rate (job-board APIs offered last 5 years still open + free + functional).
- OSS scraper survival rate (scraping-primary OSS job aggregators last 3 years still operational).
- Legal-action base rate (legal action vs technical blocking against polite scrapers).

## Source priorities

**Primary:** target sites' robots.txt (read directly); target sites' developer/API docs; hiQ Labs v. LinkedIn 9th Cir. 2022 primary text; CFAA + EU DSA Art. 40 statutory text; the six exemplar repos (READMEs, issues, post-mortems); Common Crawl job-board sitemaps; Wayback Machine ToS snapshots.

**Conditional:** Anti-bot vendor blogs (Bright Data, Apify, ScrapingBee, Oxylabs) **for empirical HTTP behavior only** — rate-limit observations, 429 triggers, response codes. Cross-validate across ≥2 such sources. **Discard their legal interpretations and any evasion recommendations.**

**Avoid:** "top 10 scraping tricks" listicles; SimilarWeb as ranking signal (sanity check only); vendor blogs as legal authority.

**Recency floors (three-tier):**
- Market/inventory: ≤6 months
- Legal: ≥ 2024-01-01
- Operational rate-limit: ≥ 2025-01-01

## Deliverable shape

Total cap: **6,000 words** excluding bibliography. Decision artifact first, reference appendix second.

1. Page 1: ranked tier table (Part 6). No prose preamble.
2. Prior-art extraction (1 paragraph × 6 exemplars).
3. Per-adapter cards (≤350 words × 8).
4. Cross-site access rules (Part 3).
5. Ban-signal taxonomy (Part 4).
6. Devil's Advocate section.
7. Legal posture paragraph (Part 5).
8. Bibliography with URLs, access dates, `[confirmed]` / `[inferred]` / `[stale]` confidence markers.

## Non-goals (expanded)

- Bypassing CAPTCHA, login walls, or paid-tier gates.
- UA rotation within a single instance (one IP many UAs is still evasion).
- TLS/HTTP fingerprint manipulation (JA3/JA4 spoofing, HTTP/2 SETTINGS munging).
- Timing jitter designed to mimic human cadence.
- Creating accounts, storing session cookies, storing OAuth tokens (exception: published API keys from official developer programs).
- Headless browser automation of any kind.
- Empirical rate discovery via testing-until-blocked.
- Aggregating beyond one user's personal use per running instance.
