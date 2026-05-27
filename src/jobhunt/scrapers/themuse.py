"""The Muse — US-focused tech job board with structured levels and categories.

Free API, no auth required (500 req/hr limit).
Endpoint: https://www.themuse.com/api/public/jobs?page=0&descending=true
Paginated by incrementing page (0-indexed, 20 results per page); capped at 500 jobs.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from datetime import datetime

from bs4 import BeautifulSoup
from dateutil import parser as dateparser

from .base import BaseScraper, RawJob

_API_URL = "https://www.themuse.com/api/public/jobs"
_PER_PAGE = 20
_MAX_JOBS = 500


class TheMuseScraper(BaseScraper):
    source = "themuse"

    async def fetch(self) -> AsyncIterator[RawJob]:
        page = 0
        total_yielded = 0
        max_pages = _MAX_JOBS // _PER_PAGE  # 25

        while page < max_pages and total_yielded < _MAX_JOBS:
            resp = await self.client.get(
                _API_URL, params={"page": page, "descending": "true"}
            )
            resp.raise_for_status()
            payload = resp.json()

            results = payload.get("results")
            if not isinstance(results, list) or not results:
                return

            page_count = payload.get("page_count", 0)

            for entry in results:
                if not isinstance(entry, dict):
                    continue

                if total_yielded >= _MAX_JOBS:
                    return

                # Parse HTML description to plain text.
                raw_html = entry.get("contents") or ""
                description = BeautifulSoup(raw_html, "lxml").get_text(
                    "\n", strip=True
                )

                # Parse publication date.
                posted_at: datetime | None = None
                if pub := entry.get("publication_date"):
                    try:
                        posted_at = dateparser.isoparse(pub)
                    except (ValueError, TypeError):
                        posted_at = None

                # Build location from locations list.
                locations = entry.get("locations") or []
                location_names = [
                    loc.get("name", "")
                    for loc in locations
                    if isinstance(loc, dict) and loc.get("name")
                ]
                location = " | ".join(location_names)

                # Determine remote status from location names.
                remote_structured = ""
                for loc_name in location_names:
                    lower = loc_name.lower()
                    if "remote" in lower or "flexible" in lower:
                        remote_structured = "remote"
                        break

                # Extract company info.
                company_obj = entry.get("company") or {}
                company_name = (
                    company_obj.get("name", "") if isinstance(company_obj, dict) else ""
                )

                # Extract URL.
                refs = entry.get("refs") or {}
                url = refs.get("landing_page", "") if isinstance(refs, dict) else ""

                # Levels and categories for extra.
                levels = entry.get("levels") or []
                level_names = [
                    lv.get("short_name", "")
                    for lv in levels
                    if isinstance(lv, dict)
                ]
                categories = entry.get("categories") or []
                category_names = [
                    cat.get("name", "")
                    for cat in categories
                    if isinstance(cat, dict)
                ]

                yield RawJob(
                    source=self.source,
                    source_id=str(entry.get("id", "")),
                    url=url,
                    company=company_name.strip(),
                    title=(entry.get("name") or "").strip(),
                    location=location,
                    description=description,
                    posted_at=posted_at,
                    remote_structured=remote_structured,
                    extra={
                        "levels": level_names,
                        "categories": category_names,
                    },
                )
                total_yielded += 1

            # Stop if we've reached the last page.
            if page >= page_count - 1:
                return
            page += 1
