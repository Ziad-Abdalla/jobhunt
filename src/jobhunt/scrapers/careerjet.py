"""Careerjet public affiliate search API — Egypt + 90 other locales.

BYO-affid, OFF by default: the endpoint 403s without a valid affiliate ID
(free partner account at careerjet.com/partners). The TODO's "easiest new
Egypt source": a clean public JSON API that indexes Wuzzuf/Bayt/company
postings for Egypt (careerjet.com.eg, locale en_EG).

Endpoint: GET http://public.api.careerjet.net/search (HTTP only — the
host publishes no TLS endpoint; only search keywords + the affid travel
on it, never user PII). Success shape per the official clients:
{"type": "JOBS", "hits": N, "pages": N, "jobs": [{title, company,
locations, salary, date, description, url, site}]}; failures use
{"type": "ERROR", "error": "..."}.

The `board` token is `"<keywords>|<location>"` (like jooble/jsearch).
A recognized country resolves the locale_code (Egypt → en_EG); anything
else is passed through as the `location` param under the default en_GB.
Offline-built against the documented shape (jsearch precedent);
live-verified 2026-07-22 (100 jobs across 2 Egypt boards) — the probe
surfaced the undocumented Referer requirement (see _REFERER).
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from datetime import datetime

from dateutil import parser as dateparser

from ..config import settings
from .base import BaseScraper, RawJob

_API_URL = "http://public.api.careerjet.net/search"
_MAX_JOBS = 50  # one page
# The API rejects referer-less calls with 403 "Undeclared referrer. Please
# add a Referer header so we know who is calling this API and from which
# page." (live-observed 2026-07-22). Any identifying page is accepted; the
# project homepage is the honest one for a locally-run app.
_REFERER = "https://github.com/Abdalla2004-collab/Jobhunt"

# Country (lowercased) → Careerjet locale. Unlisted locations fall back to
# the API default en_GB with the raw text as the `location` param — so the
# board convention is `<keywords>|<Country>`; a bare unknown city would
# search the UK index.
_LOCALES = {
    "egypt": "en_EG",
    "uk": "en_GB",
    "united kingdom": "en_GB",
    "germany": "de_DE",
    "usa": "en_US",
    "united states": "en_US",
    "france": "fr_FR",
    "netherlands": "en_NL",
    "uae": "en_AE",
    "united arab emirates": "en_AE",
    "qatar": "en_QA",
    "kuwait": "en_KW",
    "morocco": "fr_MA",
    "saudi arabia": "en_SA",
}

# Known cities → locale, keeping the city as the `location` param (a bare
# locale would silently widen "…|Cairo" to all of Egypt).
_CITY_LOCALES = {
    "cairo": "en_EG",
    "alexandria": "en_EG",
    "giza": "en_EG",
}


def _parse_board(board: str) -> tuple[str, str]:
    """`"<keywords>|<location>"` → (keywords, location)."""
    keywords, location = board, ""
    if "|" in board:
        keywords, location = board.split("|", 1)
    return keywords.strip(), location.strip()


class CareerjetScraper(BaseScraper):
    source = "careerjet"

    async def fetch(self) -> AsyncIterator[RawJob]:
        affid = settings.careerjet_affid
        if not affid:
            return

        keywords, location = _parse_board(self.board)
        if not keywords:
            return

        params: dict[str, str] = {
            "affid": affid,
            "keywords": keywords,
            # The API is designed for affiliates relaying end-user searches;
            # user_ip/user_agent are required params. jobhunt runs locally,
            # so loopback + our own UA are the honest values.
            "user_ip": "127.0.0.1",
            "user_agent": settings.user_agent,
            "pagesize": str(_MAX_JOBS),
            "page": "1",
            "sort": "date",
        }
        loc_key = location.lower()
        locale = _LOCALES.get(loc_key) if location else None
        city_locale = _CITY_LOCALES.get(loc_key) if location else None
        params["locale_code"] = locale or city_locale or "en_GB"
        if location and not locale:
            params["location"] = location

        resp = await self.client.get(_API_URL, params=params, headers={"Referer": _REFERER})
        resp.raise_for_status()
        payload = resp.json()
        if not isinstance(payload, dict) or payload.get("type") != "JOBS":
            return

        count = 0
        for entry in payload.get("jobs", []):
            if not isinstance(entry, dict):
                continue
            url = (entry.get("url") or "").strip()
            title = (entry.get("title") or "").strip()
            if not url or not title:
                continue

            posted_at: datetime | None = None
            if raw_date := entry.get("date"):
                try:
                    posted_at = dateparser.parse(raw_date)
                except (ValueError, TypeError, OverflowError):
                    posted_at = None

            yield RawJob(
                source=self.source,
                source_id=url,  # the API exposes no stable id; the URL is one
                url=url,
                company=(entry.get("company") or "").strip(),
                title=title[:256],
                location=(entry.get("locations") or "").strip(),
                description=(entry.get("description") or "").strip(),
                posted_at=posted_at,
                extra={
                    "site": entry.get("site"),
                    "salary_text": entry.get("salary"),
                },
            )
            count += 1
            if count >= _MAX_JOBS:
                break
