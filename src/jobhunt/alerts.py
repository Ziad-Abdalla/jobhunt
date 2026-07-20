"""Saved-search alerts: match new jobs against saved filters, fire notifications.

Runs after every scrape pass. Keeps a per-search list of already-notified job IDs
so the user doesn't get pinged twice for the same posting.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime

from sqlalchemy import select

from .channels import send_all
from .config import settings
from .db import db_session
from .filters import JobQuery, search
from .models import SavedSearch

log = logging.getLogger(__name__)


def _query_from_dict(data: dict) -> JobQuery:
    return JobQuery(
        q=data.get("q", ""),
        company=data.get("company", ""),
        location=data.get("location", ""),
        remote=data.get("remote", ""),
        level=data.get("level", ""),
        degree=data.get("degree", ""),
        max_years=data.get("max_years"),
        languages=tuple(data.get("languages", [])),
        skills=tuple(data.get("skills", [])),
        posted_within_days=data.get("posted_within_days"),
        limit=settings.notify_batch_max * 4,  # check more than we'll notify
        offset=0,
        sort="score",
    )


def collect_priority_sources() -> set[str]:
    """Union of `sources` across all priority saved searches — the source
    set the P7 fast-poll tier scrapes on the tight interval. A priority
    search with no source filter contributes nothing here (scraping *all*
    sources fast would defeat the point); it still benefits from the normal
    full interval."""
    out: set[str] = set()
    with db_session() as s:
        for ss in s.execute(select(SavedSearch)).scalars().all():
            data = ss.query_json or {}
            if data.get("priority"):
                out.update(data.get("sources") or [])
    return out


async def check_alerts() -> dict:
    """Iterate saved searches, find unseen matches, notify."""
    notified_total = 0
    with db_session() as s:
        searches = list(s.execute(select(SavedSearch)).scalars().all())
        for ss in searches:
            if not ss.notify:
                continue
            data = ss.query_json or {}
            q = _query_from_dict(data)
            matches = search(s, q)
            seen_ids = set(ss.notified_job_ids or [])
            new_matches = [m for m in matches if m.id not in seen_ids]
            # P7: optional per-search source filter — only alert for the
            # chosen sources when the list is non-empty.
            wanted = set(data.get("sources") or [])
            if wanted:
                new_matches = [m for m in new_matches if m.source in wanted]
            if not new_matches:
                continue
            to_notify = new_matches[: settings.notify_batch_max]
            for job in to_notify:
                send_all(
                    f"jobhunt: {ss.name}",
                    f"{job.title} @ {job.company} ({job.location or 'unknown'})",
                    url=job.url,
                )
                notified_total += 1
            ss.notified_job_ids = list(seen_ids | {m.id for m in new_matches})
            ss.last_notified_at = datetime.now(UTC)
    return {"notified": notified_total, "searches": len(searches) if searches else 0}
