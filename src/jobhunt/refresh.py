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
from .extract import extract
from .models import Job, ScrapeRun
from .salary_estimator import compute_ranges_from_db, estimate_salary
from .scoring import score_job
from .scrapers import SCRAPER_REGISTRY, BaseScraper, RawJob

log = logging.getLogger(__name__)

_EMPLOYMENT_TYPE_MAP: dict[str, str] = {
    "fulltime": "Full-time",
    "full time": "Full-time",
    "full-time": "Full-time",
    "full-time permanent": "Full-time",
    "full-time fixed-term": "Full-time",
    "permanent": "Full-time",
    "parttime": "Part-time",
    "part time": "Part-time",
    "part-time": "Part-time",
    "part-time permanent": "Part-time",
    "part-time fixed-term": "Part-time",
    "contract": "Contract",
    "contractor": "Contract",
    "freelance": "Contract",
    "temporary": "Contract",
    "short term": "Contract",
    "internship": "Internship",
    "intern": "Internship",
    "working student": "Internship",
    "apprenticeship": "Internship",
    "traineeship": "Internship",
    "volunteer": "Volunteer",
    "side": "Part-time",
    "other": "unknown",
    # German (Arbeitnow EU listings)
    "berufserfahren": "Full-time",
    "professional / experienced": "Full-time",
    "berufseinstieg": "Full-time",
    "entry": "Full-time",
    "teamleitung": "Full-time",
    "manager": "Full-time",
    "executive": "Full-time",
    "geschäftsleitung": "Full-time",
    "hilfstätigkeit / student": "Internship",
}


def _normalize_employment_type(raw: str) -> str:
    if not raw or raw == "unknown":
        return "unknown"
    return _EMPLOYMENT_TYPE_MAP.get(raw.lower().strip(), raw)


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

    # Prefer structured API data over heuristic extraction.
    remote = raw.remote_structured if raw.remote_structured else ex.remote
    # Also check location for remote signals when both API and description are silent.
    if remote == "unknown" and raw.location:
        loc_lower = raw.location.lower()
        if any(w in loc_lower for w in ("remote", "anywhere", "distributed", "worldwide")):
            remote = "remote"

    et_from_api = _normalize_employment_type(raw.employment_type)
    employment_type = et_from_api if et_from_api != "unknown" else ex.employment_type
    # Infer from level when still unknown: intern → Internship.
    if employment_type == "unknown" and ex.level == "intern":
        employment_type = "Internship"
    # Industry default: a real job posting that doesn't say part-time/contract/internship
    # is full-time. Every major job board (Indeed, LinkedIn) uses this convention.
    if employment_type == "unknown" and len(raw.description) > 50:
        employment_type = "Full-time"

    salary_min = raw.salary_min if raw.salary_min is not None else ex.salary_min
    salary_max = raw.salary_max if raw.salary_max is not None else ex.salary_max
    salary_currency = raw.salary_currency or ex.salary_currency
    salary_estimated = False

    # When no real salary data exists, estimate from level + location.
    if salary_min is None and salary_max is None:
        est = estimate_salary(ex.level, raw.location, db_ranges=db_ranges)
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
            level=ex.level,
            min_years=ex.min_years,
            degree=ex.degree,
            employment_type=employment_type,
            salary_min=salary_min,
            salary_max=salary_max,
            salary_currency=salary_currency,
            salary_estimated=salary_estimated,
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
    existing.level = ex.level
    existing.min_years = ex.min_years
    existing.degree = ex.degree
    existing.employment_type = employment_type
    existing.salary_min = salary_min if salary_min is not None else existing.salary_min
    existing.salary_max = salary_max if salary_max is not None else existing.salary_max
    existing.salary_currency = salary_currency or existing.salary_currency
    existing.salary_estimated = salary_estimated
    existing.skills = ex.skills
    existing.languages = ex.languages
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


async def scrape_all() -> dict:
    init_db()
    sources = load_sources()
    if not sources:
        return {"sources": 0, "added": 0, "seen": 0, "removed": 0}

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

        for spec, (source, raws, err) in zip(sources, results):
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
                if _persist(session, raw, company_override=spec.get("company"), db_ranges=db_ranges):
                    added += 1
                    run.jobs_added += 1
            session.add(run)

        removed = sweep_stale(session)

    return {"sources": len(sources), "added": added, "seen": seen, "removed": removed}


def sweep_stale(session: Session) -> int:
    cutoff = _utcnow() - timedelta(days=settings.stale_after_days)
    rows = session.execute(select(Job).where(Job.last_seen_at < cutoff)).scalars().all()
    for r in rows:
        session.delete(r)
    return len(rows)
