"""JSearch (RapidAPI) — indirect Egypt/MENA + worldwide-remote coverage (P8).

The plan's best *indirect* Egypt route: JSearch aggregates Google-for-Jobs
results, which surface Wuzzuf/Bayt/LinkedIn/company postings that jobhunt
can't scrape directly. BYO-key, OFF by default.

Endpoint: GET https://jsearch.p.rapidapi.com/search
Auth headers: X-RapidAPI-Key: <key>, X-RapidAPI-Host: jsearch.p.rapidapi.com
Docs: https://rapidapi.com/letscrape-6bRBa3QguO5/api/jsearch

Free tier is ~200 requests/month, so this is a LOW-FREQUENCY sweep — one page
per configured board, hard job cap. Configure it as a handful of targeted
`{source: jsearch, board: "<query>|<location>"}` entries (e.g. Egypt +
remote), NOT a firehose.

The `board` token is `"<query>|<location>"` (→ "<query> in <location>"), or
just `"<query>"`. Append `|remote` as the location to request remote-only.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from datetime import datetime

from dateutil import parser as dateparser

from ..config import settings
from .base import BaseScraper, RawJob

_API_URL = "https://jsearch.p.rapidapi.com/search"
_API_HOST = "jsearch.p.rapidapi.com"
_MAX_JOBS = 30  # one page; respect the ~200/month free tier

# JSearch job_employment_type values → the tokens refresh._EMPLOYMENT_TYPE_MAP
# already normalizes. (FULLTIME→Full-time, PARTTIME→Part-time,
# CONTRACTOR→Contract, INTERN→Internship.)
_ETYPE_MAP = {
    "FULLTIME": "fulltime",
    "PARTTIME": "parttime",
    "CONTRACTOR": "contractor",
    "CONTRACT": "contract",
    "INTERN": "intern",
    "TEMPORARY": "temporary",
}


def _parse_board(board: str) -> tuple[str, str, bool]:
    """`"<query>|<location>"` → (query, location, remote_only)."""
    query, location, remote_only = board, "", False
    if "|" in board:
        query, location = board.split("|", 1)
        if location.strip().lower() == "remote":
            remote_only, location = True, ""
    return query.strip(), location.strip(), remote_only


class JSearchScraper(BaseScraper):
    source = "jsearch"

    async def fetch(self) -> AsyncIterator[RawJob]:
        api_key = settings.jsearch_api_key
        if not api_key:
            return

        query, location, remote_only = _parse_board(self.board)
        if not query:
            return
        full_query = f"{query} in {location}" if location else query

        params: dict[str, str] = {"query": full_query, "page": "1", "num_pages": "1"}
        if remote_only:
            params["remote_jobs_only"] = "true"
        headers = {"X-RapidAPI-Key": api_key, "X-RapidAPI-Host": _API_HOST}

        resp = await self.client.get(_API_URL, params=params, headers=headers)
        resp.raise_for_status()
        payload = resp.json()

        data = payload.get("data")
        if not isinstance(data, list):
            return

        count = 0
        for entry in data:
            if not isinstance(entry, dict):
                continue
            url = entry.get("job_apply_link") or ""
            title = (entry.get("job_title") or "").strip()
            if not url or not title:
                continue

            city = (entry.get("job_city") or "").strip()
            country = (entry.get("job_country") or "").strip()
            loc = ", ".join(p for p in (city, country) if p)

            posted_at: datetime | None = None
            if dt := entry.get("job_posted_at_datetime_utc"):
                try:
                    posted_at = dateparser.parse(dt)
                except (ValueError, TypeError):
                    posted_at = None

            etype = _ETYPE_MAP.get((entry.get("job_employment_type") or "").upper(), "")
            remote = "remote" if entry.get("job_is_remote") else ""

            sal_min = entry.get("job_min_salary")
            sal_max = entry.get("job_max_salary")

            yield RawJob(
                source=self.source,
                source_id=str(entry.get("job_id", "")),
                url=url,
                company=(entry.get("employer_name") or "").strip(),
                title=title,
                location=loc,
                description=(entry.get("job_description") or "").strip(),
                posted_at=posted_at,
                employment_type=etype,
                remote_structured=remote,
                salary_min=int(sal_min) if isinstance(sal_min, (int, float)) else None,
                salary_max=int(sal_max) if isinstance(sal_max, (int, float)) else None,
                salary_currency=(entry.get("job_salary_currency") or "").strip(),
                extra={"publisher": entry.get("job_publisher")},
            )
            count += 1
            if count >= _MAX_JOBS:
                break
