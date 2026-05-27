"""Arbeitnow — EU-focused job aggregator.

Free API, no auth required.
Endpoint: https://www.arbeitnow.com/api/job-board-api
Paginated via ?page=N; response contains ``links.next`` (null when done).
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from datetime import UTC, datetime

from bs4 import BeautifulSoup

from .base import BaseScraper, RawJob

_BASE_URL = "https://www.arbeitnow.com/api/job-board-api"
_MAX_JOBS = 1000


class ArbeitnowScraper(BaseScraper):
    source = "arbeitnow"

    async def fetch(self) -> AsyncIterator[RawJob]:
        page = 1
        total_yielded = 0

        while total_yielded < _MAX_JOBS:
            resp = await self.client.get(_BASE_URL, params={"page": page})
            resp.raise_for_status()
            payload = resp.json()

            data = payload.get("data")
            if not isinstance(data, list) or not data:
                return

            for entry in data:
                if not isinstance(entry, dict):
                    continue

                if total_yielded >= _MAX_JOBS:
                    return

                # Parse HTML description to plain text.
                raw_html = entry.get("description") or ""
                description = BeautifulSoup(raw_html, "lxml").get_text(
                    "\n", strip=True
                )

                is_remote: bool = bool(entry.get("remote"))

                posted_at: datetime | None = None
                if ts := entry.get("created_at"):
                    try:
                        posted_at = datetime.fromtimestamp(int(ts), tz=UTC)
                    except (ValueError, TypeError, OSError):
                        posted_at = None

                job_types: list[str] = entry.get("job_types") or []
                employment_type = job_types[0] if job_types else None

                yield RawJob(
                    source=self.source,
                    source_id=str(entry.get("slug", "")),
                    url=entry.get("url") or "",
                    company=(entry.get("company_name") or "").strip(),
                    title=(entry.get("title") or "").strip(),
                    location=(entry.get("location") or "").strip(),
                    description=description,
                    posted_at=posted_at,
                    extra={
                        "tags": entry.get("tags", []),
                        "job_types": job_types,
                        "employment_type": employment_type,
                        "remote_structured": "remote" if is_remote else None,
                    },
                )
                total_yielded += 1

            # Follow pagination — stop when no next page.
            links = payload.get("links", {})
            if not links.get("next"):
                return
            page += 1
