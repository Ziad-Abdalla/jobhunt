"""Greenhouse Job Board public API.

Endpoint: https://boards-api.greenhouse.io/v1/boards/{board}/jobs?content=true
No auth required. Returns JSON with full job content (HTML).
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from datetime import datetime

from bs4 import BeautifulSoup
from dateutil import parser as dateparser

from .base import BaseScraper, RawJob


class GreenhouseScraper(BaseScraper):
    source = "greenhouse"

    async def fetch(self) -> AsyncIterator[RawJob]:
        url = f"https://boards-api.greenhouse.io/v1/boards/{self.board}/jobs?content=true"
        resp = await self.client.get(url)
        resp.raise_for_status()
        data = resp.json()
        for j in data.get("jobs", []):
            html = j.get("content") or ""
            description = BeautifulSoup(html, "lxml").get_text("\n", strip=True) if html else ""
            posted_at: datetime | None = None
            if updated := j.get("updated_at"):
                try:
                    posted_at = dateparser.isoparse(updated)
                except (ValueError, TypeError):
                    posted_at = None
            offices = j.get("offices") or []
            location = j.get("location", {}).get("name") or (
                ", ".join(o.get("name", "") for o in offices if o.get("name"))
            )
            yield RawJob(
                source=self.source,
                source_id=str(j.get("id", "")),
                url=j.get("absolute_url", ""),
                company=self.board.replace("-", " ").title(),
                title=j.get("title", "").strip(),
                location=(location or "").strip(),
                description=description,
                posted_at=posted_at,
                extra={"departments": [d.get("name") for d in j.get("departments", [])]},
            )
