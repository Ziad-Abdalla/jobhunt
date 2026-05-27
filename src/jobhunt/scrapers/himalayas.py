"""Himalayas — remote-only job board with rich structured data.

Free API, no auth required.
Endpoint: https://himalayas.app/jobs/api?limit=20&offset=0
Paginated by incrementing offset; capped at 500 jobs.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from datetime import datetime

from bs4 import BeautifulSoup
from dateutil import parser as dateparser

from .base import BaseScraper, RawJob

_API_URL = "https://himalayas.app/jobs/api"
_PAGE_SIZE = 20
_MAX_JOBS = 500


class HimalayasScraper(BaseScraper):
    source = "himalayas"

    async def fetch(self) -> AsyncIterator[RawJob]:
        offset = 0
        total_yielded = 0

        while total_yielded < _MAX_JOBS:
            resp = await self.client.get(
                _API_URL, params={"limit": _PAGE_SIZE, "offset": offset}
            )
            resp.raise_for_status()
            payload = resp.json()

            jobs = payload.get("jobs")
            if not isinstance(jobs, list) or not jobs:
                return

            for entry in jobs:
                if not isinstance(entry, dict):
                    continue

                if total_yielded >= _MAX_JOBS:
                    return

                # Parse HTML description to plain text.
                raw_html = entry.get("description") or ""
                description = BeautifulSoup(raw_html, "lxml").get_text(
                    "\n", strip=True
                )

                # Parse publication date.
                posted_at: datetime | None = None
                if pub := entry.get("pubDate"):
                    try:
                        posted_at = dateparser.isoparse(pub)
                    except (ValueError, TypeError):
                        posted_at = None

                # Salary fields (already numeric in the API).
                salary_min: int | None = None
                salary_max: int | None = None
                salary_currency = ""
                try:
                    raw_min = entry.get("minSalary")
                    if raw_min is not None:
                        salary_min = int(raw_min)
                except (ValueError, TypeError):
                    pass
                try:
                    raw_max = entry.get("maxSalary")
                    if raw_max is not None:
                        salary_max = int(raw_max)
                except (ValueError, TypeError):
                    pass
                if salary_min is not None or salary_max is not None:
                    salary_currency = entry.get("currency") or "USD"

                # Build location from restriction list.
                loc_restrictions = entry.get("locationRestrictions") or []
                location = ", ".join(loc_restrictions) if loc_restrictions else ""

                # Build URL — prefer applicationLink, fall back to canonical.
                job_id = entry.get("id") or ""
                url = entry.get("applicationLink") or ""
                if not url and job_id:
                    url = f"https://himalayas.app/jobs/{job_id}"

                yield RawJob(
                    source=self.source,
                    source_id=str(job_id),
                    url=url,
                    company=(entry.get("companyName") or "").strip(),
                    title=(entry.get("title") or "").strip(),
                    location=location,
                    description=description,
                    posted_at=posted_at,
                    remote_structured="remote",
                    employment_type=entry.get("employmentType") or "",
                    salary_min=salary_min,
                    salary_max=salary_max,
                    salary_currency=salary_currency,
                    extra={
                        "seniority": entry.get("seniority"),
                        "categories": entry.get("categories"),
                        "excerpt": entry.get("excerpt"),
                        "timezoneRestriction": entry.get("timezoneRestriction"),
                    },
                )
                total_yielded += 1

            # Stop if we got fewer results than a full page.
            if len(jobs) < _PAGE_SIZE:
                return
            offset += _PAGE_SIZE
