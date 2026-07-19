"""We Work Remotely — one of the largest worldwide-remote job boards.

Free per-category RSS, no auth. Board selects the category slug (e.g.
"remote-programming-jobs", "remote-design-jobs", "remote-devops-sysadmin-jobs");
empty board defaults to programming. Every WWR job is remote.

Endpoint: https://weworkremotely.com/categories/<slug>.rss
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from datetime import datetime

from bs4 import BeautifulSoup
from dateutil import parser as dateparser

from .base import BaseScraper, RawJob

_DEFAULT_CATEGORY = "remote-programming-jobs"


def _tag_text(item, name: str) -> str:
    el = item.find(name)
    return (el.text or "").strip() if el is not None and el.text else ""


class WeWorkRemotelyScraper(BaseScraper):
    source = "weworkremotely"

    async def fetch(self) -> AsyncIterator[RawJob]:
        slug = self.board or _DEFAULT_CATEGORY
        url = f"https://weworkremotely.com/categories/{slug}.rss"
        resp = await self.client.get(url)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "xml")

        for item in soup.find_all("item"):
            raw_title = _tag_text(item, "title")
            link = _tag_text(item, "link")
            if not raw_title or not link:
                continue

            # WWR titles are "Company: Role". Split off the company prefix.
            if ": " in raw_title:
                company, title = raw_title.split(": ", 1)
            else:
                company, title = "", raw_title

            description = BeautifulSoup(
                _tag_text(item, "description"), "lxml"
            ).get_text("\n", strip=True)

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
                location=_tag_text(item, "region"),
                description=description,
                posted_at=posted_at,
                remote_structured="remote",
                extra={"category": _tag_text(item, "category")},
            )
