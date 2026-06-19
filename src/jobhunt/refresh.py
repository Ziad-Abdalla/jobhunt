"""Orchestrates a full scrape pass and the stale-job sweep."""

from __future__ import annotations

import asyncio
import logging
from datetime import UTC, datetime, timedelta
from pathlib import Path

import httpx
import yaml
from sqlalchemy import select
from sqlalchemy.orm import Session

from .config import settings
from .db import db_session, init_db
from .dedup import description_hash, fingerprint
from .extract import classify_category, extract
from .models import Job, ScrapeRun
from .salary_estimator import compute_ranges_from_db, estimate_salary
from .scoring import score_job
from .scrapers import SCRAPER_REGISTRY, BaseScraper, RawJob

log = logging.getLogger(__name__)

_EMPLOYMENT_TYPE_MAP: dict[str, str] = {
    # Full-time
    "fulltime": "Full-time",
    "full time": "Full-time",
    "full-time": "Full-time",
    "ft": "Full-time",
    "full-time permanent": "Full-time",
    "full-time fixed-term": "Full-time",
    "permanent": "Full-time",
    "regular": "Full-time",
    "employee": "Full-time",
    "salaried": "Full-time",
    # Part-time
    "parttime": "Part-time",
    "part time": "Part-time",
    "part-time": "Part-time",
    "pt": "Part-time",
    "part-time permanent": "Part-time",
    "part-time fixed-term": "Part-time",
    "side": "Part-time",
    # Contract
    "contract": "Contract",
    "contractor": "Contract",
    "freelance": "Contract",
    "freelancer": "Contract",
    "temporary": "Contract",
    "temp": "Contract",
    "short term": "Contract",
    "fixed-term": "Contract",
    "fixed term": "Contract",
    "casual": "Contract",
    "per diem": "Contract",
    # Internship
    "internship": "Internship",
    "intern": "Internship",
    "working student": "Internship",
    "apprenticeship": "Internship",
    "traineeship": "Internship",
    "trainee": "Internship",
    "co-op": "Internship",
    "coop": "Internship",
    "placement": "Internship",
    "volunteer": "Internship",
    # Suppress to unknown (these are career levels, not employment types)
    "other": "unknown",
    "any": "unknown",
    # German (from Arbeitnow / Arbeitsagentur)
    "vollzeit": "Full-time",
    "teilzeit": "Part-time",
    "berufserfahren": "Full-time",
    "professional / experienced": "Full-time",
    "berufseinstieg": "Full-time",
    "entry": "Full-time",
    "teamleitung": "Full-time",
    "manager": "Full-time",
    "executive": "Full-time",
    "geschäftsleitung": "Full-time",
    "hilfstätigkeit / student": "Internship",
    "werkstudent": "Internship",
    "praktikum": "Internship",
    "minijob": "Part-time",
    "aushilfe": "Part-time",
}


def _normalize_employment_type(raw: str) -> str:
    if not raw or raw == "unknown":
        return "unknown"
    return _EMPLOYMENT_TYPE_MAP.get(raw.lower().strip(), raw)


def _resolve_level(detected_level: str, category: str, *, has_description: bool) -> str:
    """Pick a job's seniority when the title carried no explicit signal.

    A bare "Software Engineer" is mid-level by industry convention, but a bare
    "Cleaner" or "Catering Assistant" is entry-level work. Defaulting local
    (non-tech) roles to "mid" would hide them from the zero-experience filter,
    so they default to "entry" instead.
    """
    if detected_level != "unknown":
        return detected_level
    if not has_description:
        return "unknown"
    return "mid" if category == "tech" else "entry"


def load_sources() -> list[dict]:
    items: list[dict] = []
    for path in (settings.sources_file, settings.local_sources_file):
        if Path(path).exists():
            with open(path, encoding="utf-8") as f:
                loaded = yaml.safe_load(f) or []
                if isinstance(loaded, list):
                    items.extend(loaded)
    return items


def _utcnow() -> datetime:
    return datetime.now(UTC)


def _persist(
    session: Session,
    raw: RawJob,
    company_override: str | None,
    db_ranges: dict | None = None,
) -> bool:
    """Upsert a single RawJob. Returns True if it was newly added."""
    if not raw.title or not raw.url:
        return False

    is_real_name = company_override and not company_override.startswith("(")
    override = company_override if is_real_name else None
    company = override or raw.company or raw.source
    fp = fingerprint(company, raw.title, raw.location)

    existing: Job | None = session.execute(
        select(Job).where(Job.fingerprint == fp)
    ).scalar_one_or_none()

    ex = extract(raw.description, title=raw.title)
    score = score_job(
        posted_at=raw.posted_at,
        description=raw.description,
        skills=ex.skills,
        languages=ex.languages,
    )
    now = _utcnow()

    # ── Remote ──
    remote = raw.remote_structured if raw.remote_structured else ex.remote
    if remote == "unknown" and raw.location:
        loc_lower = raw.location.lower()
        remote_words = ("remote", "anywhere", "distributed", "worldwide", "global")
        if any(w in loc_lower for w in remote_words):
            remote = "remote"
    # A specific city/state location with no remote signal → onsite.
    if remote == "unknown" and raw.location and "," in raw.location:
        remote = "onsite"

    # ── Category + Level ──
    # Category first, because the level default is category-aware: an unqualified
    # tech title is mid by convention, an unqualified local title is entry-level.
    category = classify_category(raw.title, raw.description)
    level = _resolve_level(ex.level, category, has_description=len(raw.description) > 50)

    # ── Employment type ──
    et_from_api = _normalize_employment_type(raw.employment_type)
    employment_type = et_from_api if et_from_api != "unknown" else ex.employment_type
    if employment_type == "unknown" and level in ("intern",):
        employment_type = "Internship"
    if employment_type == "unknown" and level in ("entry", "junior") and len(raw.description) > 50:
        employment_type = "Full-time"
    if employment_type == "unknown" and len(raw.description) > 50:
        employment_type = "Full-time"

    salary_min = raw.salary_min if raw.salary_min is not None else ex.salary_min
    salary_max = raw.salary_max if raw.salary_max is not None else ex.salary_max
    salary_currency = raw.salary_currency or ex.salary_currency
    salary_estimated = False

    # When no real salary data exists, estimate from level + location.
    if salary_min is None and salary_max is None:
        est = estimate_salary(level, raw.location, db_ranges=db_ranges)
        salary_min = est.min_salary
        salary_max = est.max_salary
        salary_currency = est.currency
        salary_estimated = True

    if existing is None:
        job = Job(
            fingerprint=fp,
            source=raw.source,
            source_id=raw.source_id,
            url=raw.url,
            company=company,
            title=raw.title,
            location=raw.location,
            remote=remote,
            level=level,
            min_years=ex.min_years,
            degree=ex.degree,
            employment_type=employment_type,
            salary_min=salary_min,
            salary_max=salary_max,
            salary_currency=salary_currency,
            visa_sponsorship=raw.visa_sponsorship or "unknown",
            salary_estimated=salary_estimated,
            category=category,
            skills=ex.skills,
            languages=ex.languages,
            description=raw.description,
            description_hash=description_hash(raw.description),
            posted_at=raw.posted_at,
            first_seen_at=now,
            last_seen_at=now,
            score=score,
        )
        session.add(job)
        return True

    # Update existing — refresh tags + last_seen so the stale sweep keeps it alive.
    existing.last_seen_at = now
    existing.url = raw.url or existing.url
    existing.description = raw.description or existing.description
    existing.description_hash = description_hash(existing.description)
    existing.remote = remote
    existing.level = level
    existing.min_years = ex.min_years
    existing.degree = ex.degree
    existing.employment_type = employment_type
    existing.salary_min = salary_min if salary_min is not None else existing.salary_min
    existing.salary_max = salary_max if salary_max is not None else existing.salary_max
    existing.salary_currency = salary_currency or existing.salary_currency
    existing.salary_estimated = salary_estimated
    if raw.visa_sponsorship:
        existing.visa_sponsorship = raw.visa_sponsorship
    existing.skills = ex.skills
    existing.languages = ex.languages
    existing.category = category
    existing.score = score
    if raw.posted_at and not existing.posted_at:
        existing.posted_at = raw.posted_at
    return False


async def _run_scraper(
    client: httpx.AsyncClient, spec: dict, sem: asyncio.Semaphore
) -> tuple[str, list[RawJob], str | None]:
    source = spec.get("source")
    board = spec.get("board", "")
    cls: type[BaseScraper] | None = SCRAPER_REGISTRY.get(source or "")
    if cls is None:
        return (str(source), [], f"unknown source: {source}")
    async with sem:
        try:
            scraper = cls(client=client, board=board)
            jobs = [j async for j in scraper.fetch()]
            return (source, jobs, None)
        except Exception as exc:  # noqa: BLE001 — we want to log and continue per source
            log.warning("scraper %s/%s failed: %s", source, board, exc)
            return (source, [], f"{type(exc).__name__}: {exc}")


_AUTO_DISABLE_AFTER = 3  # consecutive failed scrapes before we skip a source


def _disabled_sources(session: Session) -> set[tuple[str, str]]:
    """Return (source, board) pairs that have failed _AUTO_DISABLE_AFTER
    consecutive scrapes — these are presumed dead and skipped on the next
    refresh until something changes. Defensive half of the maintenance
    hybrid: stop wasting requests on URLs that 404, while the
    source-maintenance skill researches a replacement.

    Uses a window function so we always fetch the latest N rows *per
    (source, board)*, never a global LIMIT — that guarantees behaviour is
    independent of how many total scrape_runs the DB carries.
    """
    from sqlalchemy import text as _sql_text

    rows = session.execute(_sql_text(f"""
        SELECT source, board, error, jobs_seen
        FROM (
            SELECT
                source,
                COALESCE(board, '') AS board,
                error,
                jobs_seen,
                ROW_NUMBER() OVER (
                    PARTITION BY source, COALESCE(board, '')
                    ORDER BY started_at DESC
                ) AS rn
            FROM scrape_runs
        )
        WHERE rn <= {_AUTO_DISABLE_AFTER}
    """)).all()

    from collections import defaultdict
    grouped: dict[tuple[str, str], list[tuple[str | None, int]]] = defaultdict(list)
    for source, board, error, jobs_seen in rows:
        grouped[(source, board or "")].append((error, jobs_seen or 0))

    disabled: set[tuple[str, str]] = set()
    for key, runs in grouped.items():
        if len(runs) < _AUTO_DISABLE_AFTER:
            continue
        # Only disable a source that genuinely + persistently ERRORED every recent
        # run. Two things are deliberately NOT disabling: a board that's simply
        # empty right now (jobs_seen == 0, no error — it repopulates later), and a
        # transient rate-limit/timeout (429 / TooManyRequests / Timeout), which is
        # throttling, not a dead source. Otherwise a busy refresh silently kills
        # healthy sources and "plentiful" shrinks over time.
        if all(_is_hard_error(error) for error, _ in runs):
            disabled.add(key)
    return disabled


def _is_hard_error(error: str | None) -> bool:
    """A persistent failure (404, DNS, TLS) — not an empty result or a transient
    rate-limit/timeout that should be retried rather than disabling the source."""
    if not error:
        return False
    e = error.lower()
    transient = ("429", "toomanyrequests", "rate limit", "timeout", "timed out")
    return not any(t in e for t in transient)


async def scrape_all() -> dict:
    init_db()
    sources = load_sources()

    # Auto-add Jooble searches for the user's configured location — but only when
    # it names a country ("London, UK"), not a bare city. Jooble resolves a bare
    # "London" to the wrong place (London, Kentucky), so we require the
    # disambiguating country before trusting it. Country-qualified entries in
    # sources.yaml are unaffected.
    if settings.jooble_api_key and "," in settings.user_location:
        loc = settings.user_location
        for kw in ["software developer", "software engineer", "developer"]:
            sources.append({"source": "jooble", "board": f"{kw}|{loc}"})

    if not sources:
        return {"sources": 0, "added": 0, "seen": 0, "removed": 0}

    # Filter out sources that have failed three scrapes in a row — they're
    # almost certainly dead, and continuing to hit their URLs wastes time
    # and triggers more 4xx noise in logs. Re-enables automatically on the
    # next refresh once a single scrape returns ≥1 job.
    with db_session() as s:
        disabled = _disabled_sources(s)
    skipped = 0
    if disabled:
        import random
        active = []
        for spec in sources:
            key = (spec.get("source", "?"), str(spec.get("board", "")))
            # Re-probe a disabled source ~1 run in 4 so one that recovers
            # (e.g. the company moved ATS and it's fixed) can come back, instead
            # of being skipped forever and never getting a fresh scrape_run.
            if key in disabled and random.random() >= 0.25:
                skipped += 1
                continue
            active.append(spec)
        if skipped:
            log.info("auto-disabled %d sources after %d consecutive failures",
                     skipped, _AUTO_DISABLE_AFTER)
        sources = active

    headers = {"User-Agent": settings.user_agent, "Accept": "application/json"}
    sem = asyncio.Semaphore(settings.concurrency)
    added = 0
    seen = 0
    started = _utcnow()

    async with httpx.AsyncClient(
        headers=headers, timeout=settings.request_timeout, follow_redirects=True
    ) as client:
        results = await asyncio.gather(
            *[_run_scraper(client, spec, sem) for spec in sources]
        )

    with db_session() as session:
        # Compute salary ranges from our own data for better estimates.
        db_ranges = compute_ranges_from_db(session)
        if db_ranges:
            log.info("salary estimator: %d level×region combos from own data", len(db_ranges))

        for spec, (source, raws, err) in zip(sources, results, strict=False):
            run = ScrapeRun(
                source=source or "?",
                board=str(spec.get("board", "")),
                started_at=started,
                finished_at=_utcnow(),
                jobs_seen=len(raws),
                jobs_added=0,
                jobs_removed=0,
                error=err,
            )
            for raw in raws:
                seen += 1
                company_override = spec.get("company")
                if _persist(session, raw, company_override=company_override, db_ranges=db_ranges):
                    added += 1
                    run.jobs_added += 1
            session.add(run)

        removed = sweep_stale(session)

    # Checkpoint the WAL file so it doesn't grow unbounded on long-running
    # installs. Runs PASSIVE — never blocks, never raises.
    from .db import wal_checkpoint
    wal_checkpoint()

    return {
        "sources": len(sources),
        "added": added,
        "seen": seen,
        "removed": removed,
        "skipped": skipped,
    }


def sweep_stale(session: Session) -> int:
    cutoff = _utcnow() - timedelta(days=settings.stale_after_days)
    rows = session.execute(select(Job).where(Job.last_seen_at < cutoff)).scalars().all()
    for r in rows:
        session.delete(r)
    return len(rows)
