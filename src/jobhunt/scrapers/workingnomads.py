"""Working Nomads — worldwide-remote job aggregator.

Free JSON API, no auth. Returns a flat array of currently-listed remote jobs. Board
param is ignored.

Endpoint: https://www.workingnomads.com/api/exposed_jobs/
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from datetime import datetime

from bs4 import BeautifulSoup
from dateutil import parser as dateparser

from .base import BaseScraper, RawJob

_API_URL = "https://www.workingnomads.com/api/exposed_jobs/"


class WorkingNomadsScraper(BaseScraper):
    source = "workingnomads"

    async def fetch(self) -> AsyncIterator[RawJob]:
        resp = await self.client.get(_API_URL)
        resp.raise_for_status()
        payload = resp.json()

        if not isinstance(payload, list):
            return

        for entry in payload:
            if not isinstance(entry, dict):
                continue

            url = (entry.get("url") or "").strip()
            title = (entry.get("title") or "").strip()
            if not url or not title:
                continue

            description = BeautifulSoup(
                entry.get("description") or "", "lxml"
            ).get_text("\n", strip=True)

            posted_at: datetime | None = None
            if pub := entry.get("pub_date"):
                try:
                    posted_at = dateparser.parse(pub)
                except (ValueError, TypeError, OverflowError):
                    posted_at = None

            # No stable id field — derive one from the numeric job path in the URL.
            source_id = url.rstrip("/").rsplit("/", 1)[-1] or url

            yield RawJob(
                source=self.source,
                source_id=source_id,
                url=url,
                company=(entry.get("company_name") or "").strip(),
                title=title,
                location=(entry.get("location") or "").strip(),
                description=description,
                posted_at=posted_at,
                remote_structured="remote",
                extra={
                    "category": entry.get("category_name"),
                    "tags": entry.get("tags"),
                },
            )
