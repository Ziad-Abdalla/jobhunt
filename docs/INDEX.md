# jobhunt — Knowledge Index (AI-facing manifest)

Per `~/projects/KNOWLEDGE_CONVENTION.md`. Read this first when planning in an area below. A missing row = a gap to research/audit. A stale row = re-verify (proportionate — only the area in play). The owner reads the HTML view via the `owner-hub` skill.

| Title | Path | Kind | Source | Area | Status | Date | Verdict |
|---|---|---|---|---|---|---|---|
| Multi-country enhancement design spec | `docs/superpowers/specs/2026-05-30-jobhunt-enhancement-design.md` | Spec | This session | Architecture / roadmap | DRAFT (owner review) | 2026-05-30 | 7-batch plan: resilience → countries → distance → cooldown/CV → UX → update/community → public-hardening |
| Enhancement research — synthesis | `docs/internal/research/JOBHUNT_ENHANCEMENT_2026_05_30/00-SYNTHESIS-AND-RECOMMENDATIONS.md` | Decision | Web research (ToS-verified) | Sources/geo/update/keys | CURRENT | 2026-05-30 | READ FIRST for the enhancement. |
| Free job sources (UK/DE/QA/MY/US) | `docs/internal/research/JOBHUNT_ENHANCEMENT_2026_05_30/01-free-job-sources.md` | Research | Web | Job sources | CURRENT | 2026-05-30 | Careerjet (all 5, only free QA+MY); Adzuna (UK/DE/US, ToS-gated); USAJOBS; JSearch backfill. Avoid LinkedIn/Indeed/JobStreet/Bayt. |
| Similar OSS tools / patterns to borrow | `docs/internal/research/JOBHUNT_ENHANCEMENT_2026_05_30/02-similar-oss-tools.md` | Research | Web | OSS / licensing | CURRENT | 2026-05-30 | JobSpy + JobFunnel MIT → borrow shared 429-session, dedup/recover, respectful delay. JobSpy opt-in only. |
| Free distance / geocoding stack | `docs/internal/research/JOBHUNT_ENHANCEMENT_2026_05_30/03-free-distance-geocoding.md` | Research | Web | Geocoding | CURRENT | 2026-05-30 | pgeocode + GeoNames cities15000 (offline) + Nominatim fallback; Haversine; geocode-once. QA city-level only. |
| Free + secure auto-update | `docs/internal/research/JOBHUNT_ENHANCEMENT_2026_05_30/04-free-auto-update.md` | Research | Web | Distribution/update | CURRENT | 2026-05-30 | GitHub Releases advisory notifier; pipx/pip native upgrade; SHA256 + Artifact Attestations. |
| Key resilience + community layer | `docs/internal/research/JOBHUNT_ENHANCEMENT_2026_05_30/05-key-resilience-and-community.md` | Research | Web | Resilience/community | CURRENT | 2026-05-30 | Per-source circuit breaker (classify by status); 30-min cooldown; $0 GitHub-release source manifest (never keys). |
| Data-layer rulebook + audit log | `docs/MAINTENANCE.md` | Rulebook | Project | Source maintenance | CURRENT | (pre-existing) | Source taxonomy, failure modes, repair decision tree, free-API trust hierarchy. |
