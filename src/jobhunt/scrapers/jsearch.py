"""JSearch (RapidAPI) — indirect Egypt/MENA + worldwide-remote coverage (P8).

The plan's best *indirect* Egypt route: JSearch aggregates Google-for-Jobs
results, which surface Wuzzuf/Bayt/LinkedIn/company postings that jobhunt
can't scrape directly. BYO-key, OFF by default.

Endpoint: GET https://jsearch.p.rapidapi.com/search-v2 (the original /search
was retired upstream — live-probed 2026-07-21: it 404s with "Endpoint
'/search' does not exist"; v2 wraps results as data.jobs + a cursor, adds a
`country` ISO param, and renames remote_jobs_only -> work_from_home).
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

import asyncio
import time
from collections.abc import AsyncIterator
from datetime import datetime

import httpx
from dateutil import parser as dateparser

from ..config import settings
from .base import BaseScraper, RawJob

_API_URL = "https://jsearch.p.rapidapi.com/search-v2"
_API_HOST = "jsearch.p.rapidapi.com"
_MAX_JOBS = 30  # one page; respect the ~200/month free tier

# The free tier rate-limits per second on top of the monthly quota, and
# scrape_all runs boards concurrently — unthrottled, 4 jsearch boards fire
# simultaneously and 3 get 429s (observed live). Serialize our own requests
# with spacing, and retry once after a 429.
_MIN_INTERVAL = 1.5
_RETRY_DELAY = 5.0
_last_request = 0.0

# One lock per running event loop: an asyncio.Lock binds to the loop it is
# first used on, and each test (and each asyncio.run) has its own loop.
_locks: dict[int, asyncio.Lock] = {}


def _loop_lock() -> asyncio.Lock:
    key = id(asyncio.get_running_loop())
    if key not in _locks:
        _locks.clear()
        _locks[key] = asyncio.Lock()
    return _locks[key]


async def _spaced_get(
    client: httpx.AsyncClient, params: dict[str, str], headers: dict[str, str]
) -> httpx.Response:
    global _last_request
    async with _loop_lock():
        wait = _last_request + _MIN_INTERVAL - time.monotonic()
        if wait > 0:
            await asyncio.sleep(wait)
        resp = await client.get(_API_URL, params=params, headers=headers)
        if resp.status_code == 429:
            await asyncio.sleep(_RETRY_DELAY)
            resp = await client.get(_API_URL, params=params, headers=headers)
        _last_request = time.monotonic()
    return resp

# v2's `country` ISO param beats in-query phrasing when we can resolve the
# board's location; unresolved locations fall back to "<query> in <location>"
# (which Google-for-Jobs still honors). Without a country the API defaults
# to US — so resolving matters for the Egypt use case.
_COUNTRY_CODES = {
    "egypt": "eg",
    "uk": "gb",
    "united kingdom": "gb",
    "germany": "de",
    "usa": "us",
    "united states": "us",
    "saudi arabia": "sa",
    "uae": "ae",
    "united arab emirates": "ae",
    "qatar": "qa",
    "kuwait": "kw",
    "jordan": "jo",
    "morocco": "ma",
    "france": "fr",
    "netherlands": "nl",
    "canada": "ca",
    "india": "in",
}

# JSearch job_employment_types values → the tokens refresh._EMPLOYMENT_TYPE_MAP
# already normalizes. (FULLTIME→Full-time, PARTTIME→Part-time,
# CONTRACTOR→Contract, INTERN→Internship.) v2's singular job_employment_type
# is localized display text ("دوام كامل" for country=eg) — never map from it.
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

        # language=en keeps localized display fields (job_location, the
        # singular employment type) in English when country != US.
        params: dict[str, str] = {"query": query, "language": "en"}
        if remote_only:
            params["work_from_home"] = "true"
        elif location:
            code = _COUNTRY_CODES.get(location.lower())
            if code:
                params["country"] = code
            else:
                params["query"] = f"{query} in {location}"
        headers = {"X-RapidAPI-Key": api_key, "X-RapidAPI-Host": _API_HOST}

        resp = await _spaced_get(self.client, params, headers)
        resp.raise_for_status()
        payload = resp.json()

        data = payload.get("data")
        jobs = data.get("jobs") if isinstance(data, dict) else data
        if not isinstance(jobs, list):
            return

        count = 0
        for entry in jobs:
            if not isinstance(entry, dict):
                continue
            url = entry.get("job_apply_link") or ""
            title = (entry.get("job_title") or "").strip()
            if not url or not title:
                continue

            city = (entry.get("job_city") or "").strip()
            country = (entry.get("job_country") or "").strip()
            loc = ", ".join(p for p in (city, country) if p)
            if not loc:
                # job_location may carry a "• via <publisher>" display tail.
                loc = (entry.get("job_location") or "").split("•")[0].strip()

            posted_at: datetime | None = None
            if dt := entry.get("job_posted_at_datetime_utc"):
                try:
                    posted_at = dateparser.parse(dt)
                except (ValueError, TypeError):
                    posted_at = None

            etypes = entry.get("job_employment_types")
            etoken = (
                etypes[0]
                if isinstance(etypes, list) and etypes
                else entry.get("job_employment_type") or ""
            )
            etype = _ETYPE_MAP.get(str(etoken).upper(), "")
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
