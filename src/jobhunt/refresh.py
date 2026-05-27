"""Orchestrates a full scrape pass and the stale-job sweep."""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta, timezone
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
from .scoring import score_job
from .scrapers import SCRAPER_REGISTRY, BaseScraper, RawJob

log = logging.getLogger(__name__)


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
    return datetime.now(timezone.utc)


def _persist(session: Session, raw: RawJob, company_override: str | None) -> bool:
    """Upsert a single RawJob. Returns True if it was newly added."""
    if not raw.title or not raw.url:
        return False

    company = company_override or raw.company or raw.source
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
    employment_type = raw.employment_type if raw.employment_type else "unknown"

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
            salary_min=raw.salary_min,
            salary_max=raw.salary_max,
            salary_currency=raw.salary_currency,
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
    existing.salary_min = raw.salary_min if raw.salary_min is not None else existing.salary_min
    existing.salary_max = raw.salary_max if raw.salary_max is not None else existing.salary_max
    existing.salary_currency = raw.salary_currency or existing.salary_currency
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
                if _persist(session, raw, company_override=spec.get("company")):
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
