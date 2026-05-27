"""Arbeitsagentur — Germany's official government job board (Bundesagentur fur Arbeit).

Free API with a static public key (same for everyone).
Endpoint: GET https://rest.arbeitsagentur.de/jobboerse/jobsuche-service/pc/v4/jobs
The ``board`` parameter is used as the keyword query (e.g. "Software Engineer").
"""

from __future__ import annotations

from collections.abc import AsyncIterator

from .base import BaseScraper, RawJob

_API_URL = "https://rest.arbeitsagentur.de/jobboerse/jobsuche-service/pc/v4/jobs"
_API_KEY = "jobboerse-jobsuche"  # static, public — same for everyone
_PAGE_SIZE = 25
_MAX_JOBS = 500

# arbeitszeit codes → human-readable employment type.
_ARBEITSZEIT_MAP: dict[str, str] = {
    "vz": "Full-time",
    "tz": "Part-time",
    "ho": "Remote",
    "mj": "Minijob",
}

# arbeitszeit codes that indicate remote work.
_REMOTE_CODES: set[str] = {"ho"}

_JOB_PORTAL_URL = "https://www.arbeitsagentur.de/jobsuche/suche?id="


class ArbeitsagenturScraper(BaseScraper):
    source = "arbeitsagentur"

    async def fetch(self) -> AsyncIterator[RawJob]:
        page = 1
        total_yielded = 0

        while total_yielded < _MAX_JOBS:
            params = {
                "was": self.board,
                "page": page,
                "size": _PAGE_SIZE,
                "angebotsart": 1,
            }
            headers = {"X-API-Key": _API_KEY}

            resp = await self.client.get(_API_URL, params=params, headers=headers)
            resp.raise_for_status()
            payload = resp.json()

            listings = payload.get("stellenangebote")
            if not isinstance(listings, list) or not listings:
                break

            for entry in listings:
                if not isinstance(entry, dict):
                    continue

                refnr = entry.get("refnr") or ""

                # Build location from arbeitsort.
                arbeitsort = entry.get("arbeitsort") or {}
                ort = arbeitsort.get("ort") or ""
                region = arbeitsort.get("region") or ""
                location = f"{ort}, {region}".strip(", ") if ort or region else ""

                # Map arbeitszeit to employment type and remote flag.
                arbeitszeit = (entry.get("arbeitszeit") or "").lower()
                employment_type = _ARBEITSZEIT_MAP.get(arbeitszeit, arbeitszeit)
                remote_structured = "remote" if arbeitszeit in _REMOTE_CODES else ""

                # Befristung context.
                befristung = entry.get("befristung") or ""
                contract_type = ""
                if befristung == "UNBEFRISTET":
                    contract_type = "Permanent"
                elif befristung == "BEFRISTET":
                    contract_type = "Fixed-term"

                # URL: prefer externeUrl, fall back to portal.
                url = entry.get("externeUrl") or f"{_JOB_PORTAL_URL}{refnr}"

                title = (entry.get("titel") or "").strip()

                yield RawJob(
                    source=self.source,
                    source_id=refnr,
                    url=url,
                    company=(entry.get("arbeitgeber") or "").strip(),
                    title=title,
                    location=location,
                    description=title,  # list endpoint has no description
                    employment_type=employment_type,
                    remote_structured=remote_structured,
                    extra={
                        "befristung": contract_type,
                        "eintrittsdatum": entry.get("eintrittsdatum"),
                        "plz": arbeitsort.get("plz"),
                    },
                )

                total_yielded += 1
                if total_yielded >= _MAX_JOBS:
                    break

            page += 1
