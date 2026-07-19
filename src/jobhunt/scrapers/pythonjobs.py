"""Python.org Job Board — curated Python roles worldwide.

Free RSS, no auth, zero legal risk. Low volume but high signal. Board is ignored.
Item titles are "Role, Company"; the first line of the description is the location.

Endpoint: https://www.python.org/jobs/feed/rss/
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from datetime import datetime

from bs4 import BeautifulSoup
from dateutil import parser as dateparser

from .base import BaseScraper, RawJob

_FEED_URL = "https://www.python.org/jobs/feed/rss/"


def _tag_text(item, name: str) -> str:
    el = item.find(name)
    return (el.text or "").strip() if el is not None and el.text else ""


class PythonJobsScraper(BaseScraper):
    source = "pythonjobs"

    async def fetch(self) -> AsyncIterator[RawJob]:
        resp = await self.client.get(_FEED_URL)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "xml")

        for item in soup.find_all("item"):
            raw_title = _tag_text(item, "title")
            link = _tag_text(item, "link")
            if not raw_title or not link:
                continue

            # "Role, Company" — split the trailing company off the title.
            if ", " in raw_title:
                title, company = raw_title.rsplit(", ", 1)
            else:
                title, company = raw_title, ""

            # First line of the description is the location; the rest is HTML body.
            raw_desc = _tag_text(item, "description")
            first, _, rest = raw_desc.partition("\n")
            location = first.strip()
            description = BeautifulSoup(rest, "lxml").get_text("\n", strip=True)

            posted_at: datetime | None = None
            pub = _tag_text(item, "pubDate")
            if pub:
                try:
                    posted_at = dateparser.parse(pub)
                except (ValueError, TypeError, OverflowError):
                    posted_at = None

            yield RawJob(
                source=self.source,
                source_id=_tag_text(item, "guid") or link,
                url=link,
                company=company.strip(),
                title=title.strip(),
                location=location,
                description=description,
                posted_at=posted_at,
            )
