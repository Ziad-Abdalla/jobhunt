"""P-B: the auto-queue. After each scheduled refresh, queue Applications
for jobs matching the owner's saved searches — best blended relevance
first — so gate 1 (queueing) runs on autopilot while gate 2 (the human
approve tap) stays universal.

Cowork-side module (imports the PII Application model): must never be
imported by the scrape pipeline. Scope = saved searches ONLY (owner
decision); widening is a future toggle, not a code change here.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta

from sqlalchemy import select

from .alerts import _query_from_dict
from .config import settings
from .cowork_models import Application
from .db import db_session
from .filters import search
from .models import CVProfile, Job, SavedSearch
from .scoring import home_region_from_location

log = logging.getLogger(__name__)

_EMPTY = {"queued": 0, "skipped_existing": 0, "skipped_cooldown": 0,
          "skipped_category": 0}


def auto_queue_pass() -> dict:
    """One pass over all saved searches. Returns counters for logging/UI."""
    if not settings.auto_queue:
        return dict(_EMPTY)
    out = dict(_EMPTY)
    cap = settings.auto_queue_daily_cap
    cooldown = timedelta(days=settings.auto_queue_company_cooldown_days)
    now = datetime.now(UTC)
    home = home_region_from_location(settings.user_location)
    with db_session() as s:
        cv = s.get(CVProfile, 1)
        cv_skills = {sk.lower() for sk in (cv.detected_skills or [])} if cv else set()
        existing_job_ids = {
            job_id for (job_id,) in s.execute(select(Application.job_id))
        }
        # Companies with any application created inside the cooldown window:
        # applying twice to one company in a small market hurts the owner's
        # name more than a missed posting does.
        recent_companies = {
            (c or "").strip().lower()
            for (c,) in s.execute(
                select(Job.company)
                .join(Application, Application.job_id == Job.id)
                .where(Application.created_at >= now - cooldown)
            )
        }
        queued_today = len(s.execute(
            select(Application.id).where(
                Application.queued_by == "auto",
                Application.created_at >= now.replace(
                    hour=0, minute=0, second=0, microsecond=0
                ),
            )
        ).all())
        budget = None if cap <= 0 else max(0, cap - queued_today)
        for ss in s.execute(select(SavedSearch)).scalars().all():
            data = ss.query_json or {}
            q = _query_from_dict(data)
            q.sort = "score"
            q.home_region = home
            q.limit = 50
            matches = search(s, q)
            wanted = set(data.get("sources") or [])
            if wanted:
                matches = [m for m in matches if m.source in wanted]
            for job in matches:
                if budget is not None and budget <= 0:
                    break
                if job.id in existing_job_ids:
                    out["skipped_existing"] += 1
                    continue
                company_key = (job.company or "").strip().lower()
                if company_key and company_key in recent_companies:
                    out["skipped_cooldown"] += 1
                    continue
                job_skills = {sk.lower() for sk in (job.skills or [])}
                if job.category != "tech" and not (job_skills & cv_skills):
                    out["skipped_category"] += 1
                    continue
                s.add(Application(job_id=job.id, queued_by="auto"))
                existing_job_ids.add(job.id)
                if company_key:
                    recent_companies.add(company_key)
                out["queued"] += 1
                if budget is not None:
                    budget -= 1
    if out["queued"]:
        log.info("auto-queue: %s", out)
    return out
