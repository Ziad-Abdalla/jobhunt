"""Wuzzuf — the largest job board in Egypt.

Free public RSS feed, no auth. One request returns the full firehose (thousands of
current Egyptian jobs across all sectors) with rich per-item tags. Board param is
ignored — the feed is a single all-jobs stream.

Endpoint: https://wuzzuf.net/feeds/all-jobs.xml
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from datetime import datetime

from bs4 import BeautifulSoup
from dateutil import parser as dateparser

from .base import BaseScraper, RawJob

_FEED_URL = "https://wuzzuf.net/feeds/all-jobs.xml"


def _tag_text(item, name: str) -> str:
    el = item.find(name)
    return (el.text or "").strip() if el is not None and el.text else ""


class WuzzufScraper(BaseScraper):
    source = "wuzzuf"

    async def fetch(self) -> AsyncIterator[RawJob]:
        resp = await self.client.get(_FEED_URL)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "xml")

        for item in soup.find_all("item"):
            title = _tag_text(item, "title")
            link = _tag_text(item, "link")
            if not title or not link:
                continue

            source_id = _tag_text(item, "guid") or link
            company = _tag_text(item, "source")

            # Wuzzuf is Egypt-only. Keep the city (the <area> tag) when present and
            # always carry "Egypt" so the Egypt filter + /local region map resolve it.
            area = _tag_text(item, "area")
            location = f"{area}, Egypt" if area else "Egypt"

            # Fold the requirements block into the description for richer extraction.
            description = " ".join(
                part for part in (
                    _tag_text(item, "description"),
                    _tag_text(item, "job_requirements"),
                ) if part
            ).strip()

            posted_at: datetime | None = None
            pub = _tag_text(item, "pubDate")
            if pub:
                try:
                    posted_at = dateparser.parse(pub)
                except (ValueError, TypeError, OverflowError):
                    posted_at = None

            yield RawJob(
                source=self.source,
                source_id=source_id,
                url=link,
                company=company,
                title=title,
                location=location,
                description=description,
                posted_at=posted_at,
                employment_type=_tag_text(item, "job_type"),
                extra={
                    "career_level": _tag_text(item, "career_level"),
                    "roles": _tag_text(item, "roles"),
                    "experience": _tag_text(item, "experience"),
                },
            )
