"""Workday CXS public API.

Endpoint: POST https://{tenant}.{subdomain}.myworkdayjobs.com/wday/cxs/{tenant}/{site}/jobs
No auth required. List response is JSON; detail is JSON with descriptionHTML-ish fields.

The `board` parameter has the format ``"{tenant}/{site}"`` or
``"{tenant}/{subdomain}/{site}"`` (subdomain like ``wd1``..``wd103``).
When the subdomain is omitted it defaults to ``wd5``.
"""

from __future__ import annotations

import re
from collections.abc import AsyncIterator
from datetime import datetime, timedelta, timezone

from bs4 import BeautifulSoup

from .base import BaseScraper, RawJob

_PAGE_LIMIT = 20
_DAYS_RE = re.compile(r"(\d+)\s*\+?\s*day", re.IGNORECASE)


class WorkdayScraper(BaseScraper):
    source = "workday"

    def _parse_board(self) -> tuple[str, str, str]:
        parts = self.board.split("/")
        if len(parts) == 3:
            tenant, subdomain, site = parts
        elif len(parts) == 2:
            tenant, site = parts
            subdomain = "wd5"
        else:
            raise ValueError(
                f"Invalid Workday board {self.board!r}; expected "
                "'tenant/site' or 'tenant/subdomain/site'"
            )
        return tenant, subdomain, site

    @staticmethod
    def _parse_posted_on(posted_on: str | None) -> datetime | None:
        if not posted_on:
            return None
        text = posted_on.lower()
        if "today" in text:
            return datetime.now(timezone.utc)
        if "yesterday" in text:
            return datetime.now(timezone.utc) - timedelta(days=1)
        m = _DAYS_RE.search(text)
        if m:
            try:
                days = int(m.group(1))
            except (ValueError, TypeError):
                return None
            return datetime.now(timezone.utc) - timedelta(days=days)
        return None

    @staticmethod
    def _extract_description(detail: dict) -> str:
        posting = detail.get("jobPostingInfo") or detail
        html = (
            posting.get("jobDescription")
            or posting.get("description")
            or detail.get("jobDescription")
            or ""
        )
        if not html:
            return ""
        return BeautifulSoup(html, "lxml").get_text("\n", strip=True)

    async def fetch(self) -> AsyncIterator[RawJob]:
        tenant, subdomain, site = self._parse_board()
        host = f"https://{tenant}.{subdomain}.myworkdayjobs.com"
        list_url = f"{host}/wday/cxs/{tenant}/{site}/jobs"
        body = {"appliedFacets": {}, "limit": _PAGE_LIMIT, "offset": 0, "searchText": ""}

        resp = await self.client.post(list_url, json=body)
        resp.raise_for_status()
        data = resp.json()

        postings = (data.get("jobPostings") or [])[:_PAGE_LIMIT]
        for j in postings:
            external_path = j.get("externalPath") or ""
            url = f"{host}/en-US/{site}{external_path}"
            source_id = external_path.rsplit("/", 1)[-1] or external_path

            description = ""
            if external_path:
                detail_url = f"{host}/wday/cxs/{tenant}/{site}{external_path}"
                try:
                    d_resp = await self.client.get(detail_url)
                    if d_resp.status_code == 200:
                        description = self._extract_description(d_resp.json())
                except (ValueError, TypeError):
                    description = ""

            if not description:
                bullets = j.get("bulletFields") or []
                description = "\n".join(str(b) for b in bullets if b)

            yield RawJob(
                source=self.source,
                source_id=str(source_id),
                url=url,
                company=tenant.replace("-", " ").title(),
                title=(j.get("title") or "").strip(),
                location=(j.get("locationsText") or "").strip(),
                description=description,
                posted_at=self._parse_posted_on(j.get("postedOn")),
                extra={"bullet_fields": j.get("bulletFields") or []},
            )
