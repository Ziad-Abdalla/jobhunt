"""SimplifyJobs community-maintained internship and new-grad listings.

Data sources (GitHub-hosted JSON):
- Internships: SimplifyJobs/Summer2025-Internships
- New grad: SimplifyJobs/New-Grad-Positions

Board parameter selects which feed: "internships" or "new-grad".
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from datetime import UTC, datetime

from .base import BaseScraper, RawJob

_FEEDS: dict[str, str] = {
    "internships": (
        "https://raw.githubusercontent.com/SimplifyJobs/"
        "Summer2025-Internships/dev/.github/scripts/listings.json"
    ),
    "new-grad": (
        "https://raw.githubusercontent.com/SimplifyJobs/"
        "New-Grad-Positions/dev/.github/scripts/listings.json"
    ),
}


class SimplifyJobsScraper(BaseScraper):
    source = "simplifyjobs"

    async def fetch(self) -> AsyncIterator[RawJob]:
        url = _FEEDS.get(self.board)
        if url is None:
            return

        resp = await self.client.get(url)
        resp.raise_for_status()
        items = resp.json()

        if not isinstance(items, list):
            return

        for entry in items:
            if not isinstance(entry, dict):
                continue

            # Only yield active, visible listings.
            if not entry.get("active") or not entry.get("is_visible"):
                continue

            locations: list[str] = entry.get("locations") or []
            location_str = " | ".join(locations) if locations else ""
            is_remote = any("remote" in loc.lower() for loc in locations)

            posted_at: datetime | None = None
            if ts := entry.get("date_posted"):
                try:
                    posted_at = datetime.fromtimestamp(int(ts), tz=UTC)
                except (ValueError, TypeError, OSError):
                    posted_at = None

            etype = "Internship" if self.board == "internships" else "Full-time"

            raw_sponsor = (entry.get("sponsorship") or "").lower()
            if "offer" in raw_sponsor and "not" not in raw_sponsor:
                visa = "yes"
            elif "not" in raw_sponsor:
                visa = "no"
            else:
                visa = ""

            yield RawJob(
                source=self.source,
                source_id=str(entry.get("id", "")),
                url=entry.get("url") or "",
                company=(entry.get("company_name") or "").strip(),
                title=(entry.get("title") or "").strip(),
                location=location_str,
                description="",
                posted_at=posted_at,
                employment_type=etype,
                remote_structured="remote" if is_remote else "",
                visa_sponsorship=visa,
                extra={
                    "board": self.board,
                    "terms": entry.get("terms"),
                    "category": entry.get("category"),
                    "company_url": entry.get("company_url"),
                    "date_updated": entry.get("date_updated"),
                },
            )
