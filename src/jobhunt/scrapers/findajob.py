"""Find a Job (DWP) — the UK government's free job board.

Covers all sectors, with strong coverage of zero-experience local roles
(cleaning, retail, warehouse, hospitality, care, customer service, driving).
No API key required, no rate-limit headaches.

The ``board`` parameter is "<keyword>|<location>" — same shape as Jooble. The
public RSS feed lives at:

    https://findajob.dwp.gov.uk/search?q={keyword}&w={location}&pp=50&format=rss

The feed is XML; we parse it with BeautifulSoup's lxml-xml profile to keep
dependencies the same as the rest of the codebase.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from datetime import datetime

from bs4 import BeautifulSoup
from dateutil import parser as dateparser

from .base import BaseScraper, RawJob

_FEED_URL = "https://findajob.dwp.gov.uk/search"
_PAGE_SIZE = 50
_MAX_JOBS = 200


class FindAJobScraper(BaseScraper):
    """Reads the DWP Find a Job RSS feed for a keyword + location combo."""

    source = "findajob"

    async def fetch(self) -> AsyncIterator[RawJob]:
        if "|" in self.board:
            keyword, location = self.board.split("|", 1)
        else:
            keyword = ""
            location = self.board

        params = {
            "q": keyword.strip(),
            "w": location.strip(),
            "pp": _PAGE_SIZE,
            "format": "rss",
        }
        resp = await self.client.get(_FEED_URL, params=params)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "lxml-xml")

        items = soup.find_all("item")
        seen = 0
        for entry in items:
            if seen >= _MAX_JOBS:
                break
            title = (entry.find("title").text if entry.find("title") else "").strip()
            url = (entry.find("link").text if entry.find("link") else "").strip()
            if not title or not url:
                continue

            # Description is the only field that carries the location, company,
            # and salary as a single HTML blob. Strip it for storage but leave
            # the extractors to do their normal work.
            raw_desc_node = entry.find("description")
            raw_desc = raw_desc_node.text if raw_desc_node else ""
            description = BeautifulSoup(raw_desc, "lxml").get_text("\n", strip=True)

            posted_at: datetime | None = None
            pub_node = entry.find("pubDate")
            if pub_node and pub_node.text:
                try:
                    posted_at = dateparser.parse(pub_node.text)
                except (ValueError, TypeError):
                    posted_at = None

            # Company + location aren't separate fields in the RSS — they live
            # in the description's first lines. Take a best-effort extraction.
            company = ""
            loc_field = location.strip()
            for line in description.splitlines()[:6]:
                line = line.strip()
                if not line:
                    continue
                low = line.lower()
                if low.startswith("company:"):
                    company = line.split(":", 1)[1].strip()
                elif low.startswith("location:"):
                    loc_field = line.split(":", 1)[1].strip() or loc_field

            yield RawJob(
                source=self.source,
                source_id=url.rsplit("/", 1)[-1] or url,
                url=url,
                company=company,
                title=title,
                location=loc_field,
                description=description,
                posted_at=posted_at,
                employment_type="",
                salary_min=None,
                salary_max=None,
                salary_currency="GBP",
            )
            seen += 1
