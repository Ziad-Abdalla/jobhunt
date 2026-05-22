"""Lever public postings API.

Endpoint: https://api.lever.co/v0/postings/{company}?mode=json
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from datetime import datetime, timezone

from bs4 import BeautifulSoup

from .base import BaseScraper, RawJob


class LeverScraper(BaseScraper):
    source = "lever"

    async def fetch(self) -> AsyncIterator[RawJob]:
        url = f"https://api.lever.co/v0/postings/{self.board}?mode=json"
        resp = await self.client.get(url)
        resp.raise_for_status()
        for j in resp.json():
            descr_html = j.get("description", "") + "\n" + j.get("descriptionPlain", "")
            description = BeautifulSoup(descr_html, "lxml").get_text("\n", strip=True)
            posted_at: datetime | None = None
            if created := j.get("createdAt"):
                # Lever uses ms since epoch.
                try:
                    posted_at = datetime.fromtimestamp(created / 1000, tz=timezone.utc)
                except (ValueError, TypeError):
                    posted_at = None
            categories = j.get("categories", {}) or {}
            location = categories.get("location", "") or ""
            yield RawJob(
                source=self.source,
                source_id=str(j.get("id", "")),
                url=j.get("hostedUrl", "") or j.get("applyUrl", ""),
                company=self.board.replace("-", " ").title(),
                title=(j.get("text") or "").strip(),
                location=location.strip(),
                description=description,
                posted_at=posted_at,
                extra={
                    "team": categories.get("team"),
                    "commitment": categories.get("commitment"),
                    "department": categories.get("department"),
                },
            )
