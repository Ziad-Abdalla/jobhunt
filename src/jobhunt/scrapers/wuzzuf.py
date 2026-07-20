"""Wuzzuf — the largest job board in Egypt.

Free public RSS feed, no auth. One request returns the full firehose (thousands of
current Egyptian jobs across all sectors) with rich per-item tags. Board param is
ignored — the feed is a single all-jobs stream.

Endpoint: https://wuzzuf.net/feeds/all-jobs.xml
"""

from __future__ import annotations

import re
from collections.abc import AsyncIterator
from datetime import datetime

from bs4 import BeautifulSoup
from dateutil import parser as dateparser

from .base import BaseScraper, RawJob

_FEED_URL = "https://wuzzuf.net/feeds/all-jobs.xml"

# Wuzzuf's <career_level> vocabulary → jobhunt's level values. Structured
# metadata beats regex guessing — especially for Arabic-language postings.
_CAREER_LEVEL_MAP = {
    "student": "intern",
    "entry level": "entry",
    "experienced (non-manager)": "mid",
    "manager": "lead",
}

_EXPERIENCE_RE = re.compile(r"(\d+)")


def _map_career_level(raw: str) -> str:
    key = raw.lower().strip()
    if key.startswith("senior management"):
        return "senior"
    return _CAREER_LEVEL_MAP.get(key, "")


def _parse_experience_years(raw: str) -> int | None:
    if "no exp" in raw.lower():
        return None
    m = _EXPERIENCE_RE.search(raw)
    return int(m.group(1)) if m else None


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

            career_level = _tag_text(item, "career_level")
            experience = _tag_text(item, "experience")

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
                level_structured=_map_career_level(career_level),
                min_years_structured=_parse_experience_years(experience),
                extra={
                    "career_level": career_level,
                    "roles": _tag_text(item, "roles"),
                    "experience": experience,
                },
            )
