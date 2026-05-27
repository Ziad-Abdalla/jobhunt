"""Jobicy — remote-only job board with structured salary and level data.

Free API, no auth required.
Endpoint: https://jobicy.com/api/v2/remote-jobs?count=50
Returns up to 50 jobs in a single request (no pagination needed).
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from datetime import datetime

from bs4 import BeautifulSoup
from dateutil import parser as dateparser

from .base import BaseScraper, RawJob

_API_URL = "https://jobicy.com/api/v2/remote-jobs"

# Normalise Jobicy's snake_case job types to human-readable labels.
_JOB_TYPE_MAP: dict[str, str] = {
    "full_time": "Full-time",
    "full-time": "Full-time",
    "part_time": "Part-time",
    "part-time": "Part-time",
    "contract": "Contract",
    "internship": "Internship",
    "freelance": "Freelance",
    "temporary": "Temporary",
}


class JobicyScraper(BaseScraper):
    source = "jobicy"

    async def fetch(self) -> AsyncIterator[RawJob]:
        resp = await self.client.get(_API_URL, params={"count": 50})
        resp.raise_for_status()
        payload = resp.json()

        jobs = payload.get("jobs")
        if not isinstance(jobs, list):
            return

        for entry in jobs:
            if not isinstance(entry, dict):
                continue

            # Parse HTML description to plain text.
            raw_html = entry.get("jobDescription") or ""
            description = BeautifulSoup(raw_html, "lxml").get_text(
                "\n", strip=True
            )

            # Parse publication date.
            posted_at: datetime | None = None
            if pub := entry.get("pubDate"):
                try:
                    posted_at = dateparser.parse(pub)
                except (ValueError, TypeError):
                    posted_at = None

            # Parse salary fields.
            salary_min: int | None = None
            salary_max: int | None = None
            salary_currency = ""
            try:
                raw_min = entry.get("annualSalaryMin")
                if raw_min is not None and str(raw_min).strip():
                    salary_min = int(raw_min)
            except (ValueError, TypeError):
                pass
            try:
                raw_max = entry.get("annualSalaryMax")
                if raw_max is not None and str(raw_max).strip():
                    salary_max = int(raw_max)
            except (ValueError, TypeError):
                pass
            if salary_min is not None or salary_max is not None:
                salary_currency = entry.get("salaryCurrency") or "USD"

            # Normalise employment type.
            job_types: list[str] = entry.get("jobType") or []
            employment_type = ""
            if job_types:
                raw_type = job_types[0] if isinstance(job_types, list) else str(job_types)
                employment_type = _JOB_TYPE_MAP.get(raw_type, raw_type)

            yield RawJob(
                source=self.source,
                source_id=str(entry.get("id", "")),
                url=entry.get("url") or "",
                company=(entry.get("companyName") or "").strip(),
                title=(entry.get("jobTitle") or "").strip(),
                location=(entry.get("jobGeo") or "").strip(),
                description=description,
                posted_at=posted_at,
                remote_structured="remote",
                employment_type=employment_type,
                salary_min=salary_min,
                salary_max=salary_max,
                salary_currency=salary_currency,
                extra={
                    "jobLevel": entry.get("jobLevel"),
                    "jobIndustry": entry.get("jobIndustry"),
                    "jobExcerpt": entry.get("jobExcerpt"),
                },
            )
