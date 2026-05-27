"""Ashby public job board API.

Endpoint: https://api.ashbyhq.com/posting-api/job-board/{org}?includeCompensation=true
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from datetime import datetime

from bs4 import BeautifulSoup
from dateutil import parser as dateparser

from .base import BaseScraper, RawJob


class AshbyScraper(BaseScraper):
    source = "ashby"

    async def fetch(self) -> AsyncIterator[RawJob]:
        url = (
            f"https://api.ashbyhq.com/posting-api/job-board/{self.board}"
            f"?includeCompensation=true"
        )
        resp = await self.client.get(url)
        resp.raise_for_status()
        data = resp.json()
        for j in data.get("jobs", []):
            html = j.get("descriptionHtml", "") or j.get("descriptionPlain", "")
            description = BeautifulSoup(html, "lxml").get_text("\n", strip=True)
            posted_at: datetime | None = None
            if pub := j.get("publishedAt"):
                try:
                    posted_at = dateparser.isoparse(pub)
                except (ValueError, TypeError):
                    posted_at = None
            # Extract structured compensation data.
            comp = j.get("compensation") or {}
            comp_summary = (
                comp.get("compensationTierSummary")
                or comp.get("summaryText")
                or ""
            )
            salary_min: int | None = None
            salary_max: int | None = None
            salary_currency = ""
            if isinstance(comp.get("compensationTiers"), list):
                for tier in comp["compensationTiers"]:
                    raw_min = tier.get("min")
                    salary_min = raw_min if raw_min is not None else salary_min
                    raw_max = tier.get("max")
                    salary_max = raw_max if raw_max is not None else salary_max
                    salary_currency = tier.get("currency") or salary_currency
                    break

            yield RawJob(
                source=self.source,
                source_id=str(j.get("id", "")),
                url=j.get("jobUrl") or j.get("applyUrl") or "",
                company=self.board.replace("-", " ").title(),
                title=(j.get("title") or "").strip(),
                location=(j.get("location") or "").strip(),
                description=description,
                posted_at=posted_at,
                employment_type=(j.get("employmentType") or "").strip(),
                salary_min=salary_min,
                salary_max=salary_max,
                salary_currency=salary_currency,
                extra={
                    "department": j.get("department"),
                    "team": j.get("team"),
                    "compensation_summary": comp_summary or None,
                },
            )
