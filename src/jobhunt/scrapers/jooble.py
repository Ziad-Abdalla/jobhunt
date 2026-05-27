"""Jooble — global job aggregator covering 69 countries.

Free API with key registration at https://jooble.org/api/about.
Endpoint: POST https://jooble.org/api/{api_key}
The ``board`` parameter is used as the location/country query.
"""

from __future__ import annotations

import re
from collections.abc import AsyncIterator
from datetime import datetime

from bs4 import BeautifulSoup
from dateutil import parser as dateparser

from ..config import settings
from .base import BaseScraper, RawJob

_API_BASE = "https://jooble.org/api"
_MAX_JOBS = 50  # Conservative: 1 page per country to stay within the 500-request key limit

# Pattern to extract salary range: "$60,000 - $90,000", "£30,000 - £40,000", etc.
_SALARY_RE = re.compile(
    r"[\$\£\€]?\s*([\d,]+)\s*[-–—]\s*[\$\£\€]?\s*([\d,]+)",
)

# Map common currency symbols to ISO codes.
_CURRENCY_SYMBOL_MAP: dict[str, str] = {
    "$": "USD",
    "£": "GBP",
    "€": "EUR",
}
_CURRENCY_SYMBOL_RE = re.compile(r"([\$\£\€])")


def _parse_salary(raw: str) -> tuple[int | None, int | None, str]:
    """Try to extract min, max, and currency from a free-text salary string."""
    if not raw:
        return None, None, ""

    m = _SALARY_RE.search(raw)
    if not m:
        return None, None, ""

    try:
        sal_min = int(m.group(1).replace(",", ""))
        sal_max = int(m.group(2).replace(",", ""))
    except (ValueError, TypeError):
        return None, None, ""

    currency = ""
    sym_match = _CURRENCY_SYMBOL_RE.search(raw)
    if sym_match:
        currency = _CURRENCY_SYMBOL_MAP.get(sym_match.group(1), "")

    return sal_min, sal_max, currency


class JoobleScraper(BaseScraper):
    source = "jooble"

    async def fetch(self) -> AsyncIterator[RawJob]:
        api_key = settings.jooble_api_key
        if not api_key:
            return

        url = f"{_API_BASE}/{api_key}"
        page = 1
        total_yielded = 0

        while total_yielded < _MAX_JOBS:
            body = {
                "keywords": "",
                "location": self.board,
                "page": str(page),
            }
            resp = await self.client.post(url, json=body)
            resp.raise_for_status()
            payload = resp.json()

            jobs = payload.get("jobs")
            if not isinstance(jobs, list) or not jobs:
                break

            for entry in jobs:
                if not isinstance(entry, dict):
                    continue

                # Parse HTML snippet to plain text.
                raw_html = entry.get("snippet") or ""
                description = BeautifulSoup(raw_html, "lxml").get_text(
                    "\n", strip=True,
                )

                # Parse date.
                posted_at: datetime | None = None
                if updated := entry.get("updated"):
                    try:
                        posted_at = dateparser.parse(updated)
                    except (ValueError, TypeError):
                        posted_at = None

                # Parse salary.
                salary_min, salary_max, salary_currency = _parse_salary(
                    entry.get("salary") or "",
                )

                yield RawJob(
                    source=self.source,
                    source_id=str(entry.get("id", "")),
                    url=entry.get("link") or "",
                    company=(entry.get("company") or "").strip(),
                    title=(entry.get("title") or "").strip(),
                    location=(entry.get("location") or "").strip(),
                    description=description,
                    posted_at=posted_at,
                    employment_type=(entry.get("type") or "").strip(),
                    salary_min=salary_min,
                    salary_max=salary_max,
                    salary_currency=salary_currency,
                    extra={
                        "source_board": entry.get("source"),
                    },
                )

                total_yielded += 1
                if total_yielded >= _MAX_JOBS:
                    break

            page += 1
