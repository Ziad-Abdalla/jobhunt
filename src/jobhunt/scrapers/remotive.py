"""Remotive — curated worldwide-remote job board.

Free JSON API, no auth. Board param optionally selects a category (e.g. "software-dev");
empty board returns all categories. Per Remotive's terms, poll sparingly (a few times a
day) and keep attribution — jobhunt links back to the Remotive job URL.

Endpoint: https://remotive.com/api/remote-jobs[?category=<slug>]
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from datetime import datetime

from bs4 import BeautifulSoup
from dateutil import parser as dateparser

from .base import BaseScraper, RawJob

_API_URL = "https://remotive.com/api/remote-jobs"


class RemotiveScraper(BaseScraper):
    source = "remotive"

    async def fetch(self) -> AsyncIterator[RawJob]:
        params = {"category": self.board} if self.board else {}
        resp = await self.client.get(_API_URL, params=params)
        resp.raise_for_status()
        payload = resp.json()

        jobs = payload.get("jobs")
        if not isinstance(jobs, list):
            return

        for entry in jobs:
            if not isinstance(entry, dict):
                continue

            description = BeautifulSoup(
                entry.get("description") or "", "lxml"
            ).get_text("\n", strip=True)

            posted_at: datetime | None = None
            if pub := entry.get("publication_date"):
                try:
                    posted_at = dateparser.parse(pub)
                except (ValueError, TypeError, OverflowError):
                    posted_at = None

            # Remotive uses "full_time" / "part_time"; the pipeline's map keys on the
            # hyphenated form, so bridge the underscore here.
            employment_type = (entry.get("job_type") or "").replace("_", "-")

            yield RawJob(
                source=self.source,
                source_id=str(entry.get("id", "")),
                url=entry.get("url") or "",
                company=(entry.get("company_name") or "").strip(),
                title=(entry.get("title") or "").strip(),
                location=(entry.get("candidate_required_location") or "").strip(),
                description=description,
                posted_at=posted_at,
                employment_type=employment_type,
                remote_structured="remote",
                extra={
                    "category": entry.get("category"),
                    "tags": entry.get("tags"),
                    "salary": entry.get("salary"),
                },
            )
