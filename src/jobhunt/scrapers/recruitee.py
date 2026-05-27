"""Recruitee public offers API.

Endpoint: https://{board}.recruitee.com/api/offers/
No auth required. Returns JSON with `offers` array.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from datetime import datetime

from bs4 import BeautifulSoup
from dateutil import parser as dateparser

from .base import BaseScraper, RawJob


class RecruiteeScraper(BaseScraper):
    source = "recruitee"

    async def fetch(self) -> AsyncIterator[RawJob]:
        url = f"https://{self.board}.recruitee.com/api/offers/"
        resp = await self.client.get(url)
        resp.raise_for_status()
        data = resp.json()
        for j in data.get("offers", []):
            html = (j.get("description") or "") + "\n" + (j.get("requirements") or "")
            description = BeautifulSoup(html, "lxml").get_text("\n", strip=True)
            posted_at: datetime | None = None
            if created := j.get("created_at"):
                try:
                    posted_at = dateparser.isoparse(created)
                except (ValueError, TypeError):
                    posted_at = None
            location = ", ".join(
                v for v in [j.get("city"), j.get("country")] if v
            )
            slug = j.get("slug", "")
            url_value = j.get("careers_url") or (
                f"https://{self.board}.recruitee.com/o/{slug}" if slug else ""
            )
            yield RawJob(
                source=self.source,
                source_id=str(j.get("id", "")),
                url=url_value,
                company=self.board.replace("-", " ").title(),
                title=(j.get("title") or "").strip(),
                location=location.strip(),
                description=description,
                posted_at=posted_at,
                employment_type=(j.get("employment_type_code") or "").strip(),
                extra={
                    "min_hours": j.get("min_hours"),
                    "max_hours": j.get("max_hours"),
                },
            )
