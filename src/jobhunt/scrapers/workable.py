"""Workable public job board API.

Endpoint: https://apply.workable.com/api/v3/accounts/{board}/jobs
Pagination via `paging.next`. Per-job detail at
https://apply.workable.com/api/v3/accounts/{board}/jobs/{shortcode}.

Some accounts (e.g. huggingface, live-probed 2026-07-21) 404 on the v3
widget API but still publish through the older v1 widget API
(https://apply.workable.com/api/v1/widget/accounts/{board}?details=true) —
v3 404 falls back to v1 before giving up.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from datetime import datetime

from bs4 import BeautifulSoup
from dateutil import parser as dateparser

from .base import BaseScraper, RawJob


class WorkableScraper(BaseScraper):
    source = "workable"

    async def fetch(self) -> AsyncIterator[RawJob]:
        url: str | None = (
            f"https://apply.workable.com/api/v3/accounts/{self.board}/jobs"
        )
        seen = 0
        max_jobs = 500
        first_page = True
        while url and seen < max_jobs:
            resp = await self.client.get(url)
            if resp.status_code == 404 and first_page:
                async for job in self._fetch_v1():
                    yield job
                return
            first_page = False
            resp.raise_for_status()
            data = resp.json()
            for j in data.get("jobs", []):
                if seen >= max_jobs:
                    break
                shortcode = j.get("shortcode", "")
                html = j.get("description", "") or ""
                if not html and shortcode:
                    detail_url = (
                        f"https://apply.workable.com/api/v3/accounts/"
                        f"{self.board}/jobs/{shortcode}"
                    )
                    detail_resp = await self.client.get(detail_url)
                    detail_resp.raise_for_status()
                    detail = detail_resp.json()
                    html = detail.get("description", "") or ""
                description = (
                    BeautifulSoup(html, "lxml").get_text("\n", strip=True) if html else ""
                )
                posted_at: datetime | None = None
                if created := j.get("created_at"):
                    try:
                        posted_at = dateparser.isoparse(created)
                    except (ValueError, TypeError):
                        posted_at = None
                loc_obj = j.get("location") or {}
                location_parts = [
                    loc_obj.get("city") or "",
                    loc_obj.get("region") or "",
                    loc_obj.get("country") or "",
                ]
                location = ", ".join(p for p in location_parts if p)
                yield RawJob(
                    source=self.source,
                    source_id=str(shortcode or j.get("id", "")),
                    url=j.get("url") or j.get("shortlink") or "",
                    company=self.board.replace("-", " ").title(),
                    title=(j.get("title") or "").strip(),
                    location=location.strip(),
                    description=description,
                    posted_at=posted_at,
                    employment_type=(j.get("employment_type") or "").strip(),
                    extra={
                        "department": j.get("department"),
                    },
                )
                seen += 1
            paging = data.get("paging") or {}
            url = paging.get("next")

    async def _fetch_v1(self) -> AsyncIterator[RawJob]:
        """Older v1 accounts API: flat job objects, no pagination, full
        description inline when details=true."""
        # www.workable.com/api/accounts/{board} 302s here; hit it directly
        # (the scraper client doesn't follow redirects).
        resp = await self.client.get(
            f"https://apply.workable.com/api/v1/widget/accounts/{self.board}",
            params={"details": "true"},
        )
        resp.raise_for_status()
        data = resp.json()
        for j in data.get("jobs", [])[:500]:  # same cap as the v3 path
            html = j.get("description", "") or ""
            description = (
                BeautifulSoup(html, "lxml").get_text("\n", strip=True) if html else ""
            )
            posted_at: datetime | None = None
            if created := (j.get("created_at") or j.get("published_on")):
                try:
                    posted_at = dateparser.isoparse(created)
                except (ValueError, TypeError):
                    posted_at = None
            location_parts = [
                j.get("city") or "",
                j.get("state") or "",
                j.get("country") or "",
            ]
            location = ", ".join(p for p in location_parts if p)
            yield RawJob(
                source=self.source,
                source_id=str(j.get("shortcode", "")),
                url=j.get("url") or j.get("shortlink") or "",
                company=data.get("name") or self.board.replace("-", " ").title(),
                title=(j.get("title") or "").strip(),
                location=location.strip(),
                description=description,
                posted_at=posted_at,
                employment_type=(j.get("employment_type") or "").strip(),
                remote_structured="remote" if j.get("telecommuting") else "",
                extra={"department": j.get("department")},
            )
