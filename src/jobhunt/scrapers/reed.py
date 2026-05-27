"""Reed.co.uk — UK's largest job board.

Free API with key registration at https://www.reed.co.uk/developers/jobseeker.
Auth: Basic auth with API key as username, empty password.
Endpoint: GET https://www.reed.co.uk/api/1.0/search
The ``board`` parameter is used as the keyword query.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from datetime import datetime

import httpx
from bs4 import BeautifulSoup
from dateutil import parser as dateparser

from ..config import settings
from .base import BaseScraper, RawJob

_API_URL = "https://www.reed.co.uk/api/1.0/search"
_PAGE_SIZE = 100
_MAX_JOBS = 500


class ReedScraper(BaseScraper):
    source = "reed"

    async def fetch(self) -> AsyncIterator[RawJob]:
        api_key = settings.reed_api_key
        if not api_key:
            return

        auth = httpx.BasicAuth(username=api_key, password="")
        offset = 0
        total_yielded = 0

        while total_yielded < _MAX_JOBS:
            params = {
                "keywords": self.board,
                "resultsToTake": _PAGE_SIZE,
                "resultsToSkip": offset,
            }
            resp = await self.client.get(_API_URL, params=params, auth=auth)
            resp.raise_for_status()
            payload = resp.json()

            results = payload.get("results")
            if not isinstance(results, list) or not results:
                break

            for entry in results:
                if not isinstance(entry, dict):
                    continue

                # Parse HTML description.
                raw_html = entry.get("jobDescription") or ""
                description = BeautifulSoup(raw_html, "lxml").get_text(
                    "\n", strip=True,
                )

                # Parse date.
                posted_at: datetime | None = None
                if date_str := entry.get("date"):
                    try:
                        posted_at = dateparser.parse(date_str)
                    except (ValueError, TypeError):
                        posted_at = None

                # Salary fields come as numbers from the API.
                salary_min: int | None = None
                salary_max: int | None = None
                try:
                    raw_min = entry.get("minimumSalary")
                    if raw_min is not None:
                        salary_min = int(raw_min)
                except (ValueError, TypeError):
                    pass
                try:
                    raw_max = entry.get("maximumSalary")
                    if raw_max is not None:
                        salary_max = int(raw_max)
                except (ValueError, TypeError):
                    pass

                salary_currency = ""
                if salary_min is not None or salary_max is not None:
                    salary_currency = entry.get("currency") or "GBP"

                yield RawJob(
                    source=self.source,
                    source_id=str(entry.get("jobId", "")),
                    url=entry.get("jobUrl") or "",
                    company=(entry.get("employerName") or "").strip(),
                    title=(entry.get("jobTitle") or "").strip(),
                    location=(entry.get("locationName") or "").strip(),
                    description=description,
                    posted_at=posted_at,
                    employment_type=(entry.get("employmentType") or "").strip(),
                    salary_min=salary_min,
                    salary_max=salary_max,
                    salary_currency=salary_currency,
                    extra={
                        "expirationDate": entry.get("expirationDate"),
                    },
                )

                total_yielded += 1
                if total_yielded >= _MAX_JOBS:
                    break

            offset += _PAGE_SIZE
