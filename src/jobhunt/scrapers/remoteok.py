"""RemoteOK public API.

Endpoint: https://remoteok.com/api  (returns JSON list; first element is metadata)
RemoteOK asks for a UA other than the default httpx one.
"""

from __future__ import annotations

import re
from collections.abc import AsyncIterator
from datetime import datetime

from bs4 import BeautifulSoup
from dateutil import parser as dateparser

from .base import BaseScraper, RawJob

_SALARY_RE = re.compile(
    r"\$?\s*([\d,]+)\s*(?:[-–—to]+)\s*\$?\s*([\d,]+)", re.IGNORECASE
)


class RemoteOKScraper(BaseScraper):
    source = "remoteok"

    async def fetch(self) -> AsyncIterator[RawJob]:
        # `self.board` is treated as a tag filter (e.g. "dev"); empty fetches everything.
        url = "https://remoteok.com/api"
        if self.board and self.board not in ("", "*", "all"):
            url = f"https://remoteok.com/api?tags={self.board}"
        resp = await self.client.get(url)
        resp.raise_for_status()
        items = resp.json()
        if not isinstance(items, list):
            return
        for j in items:
            if not isinstance(j, dict) or "id" not in j:
                continue  # skip metadata header
            description = BeautifulSoup(j.get("description", ""), "lxml").get_text(
                "\n", strip=True
            )
            posted_at: datetime | None = None
            if pub := j.get("date"):
                try:
                    posted_at = dateparser.isoparse(pub)
                except (ValueError, TypeError):
                    posted_at = None
            # Parse salary string (e.g. "$60,000 - $90,000").
            salary_raw = j.get("salary") or ""
            salary_min: int | None = None
            salary_max: int | None = None
            salary_currency = ""
            if salary_raw:
                m = _SALARY_RE.search(salary_raw)
                if m:
                    try:
                        salary_min = int(m.group(1).replace(",", ""))
                        salary_max = int(m.group(2).replace(",", ""))
                    except (ValueError, TypeError):
                        pass
                # RemoteOK salaries are USD unless stated otherwise.
                if salary_min is not None or salary_max is not None:
                    salary_currency = "USD"

            yield RawJob(
                source=self.source,
                source_id=str(j.get("id", "")),
                url=j.get("url") or j.get("apply_url") or "",
                company=(j.get("company") or "").strip(),
                title=(j.get("position") or "").strip(),
                location=(j.get("location") or "Remote").strip(),
                description=description,
                posted_at=posted_at,
                remote_structured="remote",
                salary_min=salary_min,
                salary_max=salary_max,
                salary_currency=salary_currency,
                extra={"tags": j.get("tags", [])},
            )
