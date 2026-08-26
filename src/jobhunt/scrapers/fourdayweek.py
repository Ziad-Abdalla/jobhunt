"""4dayweek.io — remote + four-day-week job board with a free JSON API.

No auth. Paginated via ``?page=N&limit=100``; the response carries
``total`` and ``has_more``. The API ignores server-side filters, so
category and remote-only filtering happen here.

What makes this source worth having: every job states a
``work_arrangement`` (remote / hybrid / onsite) plus the country and
continent of each location. Most remote boards collapse that to the word
"remote", which hides whether a role is actually open outside one country.

Note: the company object embedded in the list response is a stub — its
``hires_worldwide`` flag reads False for every row and its timestamps are
zero values, so it is deliberately not read here. Judge eligibility from
``work_arrangement`` plus the location countries instead.

Endpoint: https://4dayweek.io/api/jobs?page=<n>&limit=100
Job URL:  https://4dayweek.io/job/<slug>
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from datetime import UTC, datetime

from .base import BaseScraper, RawJob

_API_URL = "https://4dayweek.io/api/jobs"
_JOB_URL = "https://4dayweek.io/job/{slug}"
_PAGE_SIZE = 100
_MAX_JOBS = 1000


def _location_text(entry: dict) -> str:
    """Flatten the locations array into one human string, primary first."""
    locations = entry.get("locations")
    if not isinstance(locations, list):
        return ""
    parts: list[str] = []
    for loc in locations:
        if not isinstance(loc, dict):
            continue
        bits = [loc.get("city"), loc.get("state"), loc.get("country")]
        text = ", ".join(b for b in bits if b)
        if not text:
            continue
        if loc.get("is_primary"):
            parts.insert(0, text)
        else:
            parts.append(text)
    return " | ".join(dict.fromkeys(parts))


class FourDayWeekScraper(BaseScraper):
    source = "4dayweek"

    async def fetch(self) -> AsyncIterator[RawJob]:
        # board selects a category slug (e.g. "engineering"); empty = all.
        wanted_category = self.board.strip().lower()
        page = 1
        total_yielded = 0

        while total_yielded < _MAX_JOBS:
            resp = await self.client.get(
                _API_URL, params={"page": page, "limit": _PAGE_SIZE}
            )
            # The board is free and unauthenticated; a 403/429 mid-walk means
            # "that's enough" rather than a real failure. Stop rather than
            # bubbling an exception that would kill the whole refresh.
            if resp.status_code in (403, 429):
                return
            resp.raise_for_status()
            payload = resp.json()

            jobs = payload.get("jobs")
            if not isinstance(jobs, list) or not jobs:
                return

            for entry in jobs:
                if not isinstance(entry, dict) or entry.get("is_expired"):
                    continue
                if wanted_category and (
                    str(entry.get("category") or "").lower() != wanted_category
                ):
                    continue

                slug = entry.get("slug") or ""
                if not slug:
                    continue

                posted_at: datetime | None = None
                if isinstance(posted := entry.get("posted"), int | float):
                    try:
                        posted_at = datetime.fromtimestamp(posted, tz=UTC)
                    except (ValueError, OSError, OverflowError):
                        posted_at = None

                company = entry.get("company")
                company = company if isinstance(company, dict) else {}
                stack = entry.get("stack")
                tags = [
                    s.get("name")
                    for s in (stack if isinstance(stack, list) else [])
                    if isinstance(s, dict) and s.get("name")
                ]

                yield RawJob(
                    source=self.source,
                    source_id=str(entry.get("id", "")),
                    url=_JOB_URL.format(slug=slug),
                    company=(entry.get("company_name") or "").strip(),
                    title=(entry.get("title") or "").strip(),
                    location=_location_text(entry),
                    posted_at=posted_at,
                    remote_structured=(entry.get("work_arrangement") or "").strip(),
                    extra={
                        "category": entry.get("category"),
                        "tags": tags,
                        "schedule_type": entry.get("schedule_type"),
                        "work_life_score": entry.get("work_life_score"),
                        "company_slug": company.get("slug"),
                    },
                )
                total_yielded += 1

            if not payload.get("has_more"):
                return
            page += 1
