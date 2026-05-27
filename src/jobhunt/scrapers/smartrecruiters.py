"""SmartRecruiters public postings API.

List endpoint: https://api.smartrecruiters.com/v1/companies/{board}/postings
Detail endpoint: .../postings/{id} returns jobAd.sections.{jobDescription,qualifications,responsibilities}.text
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from datetime import datetime

from bs4 import BeautifulSoup
from dateutil import parser as dateparser

from .base import BaseScraper, RawJob


class SmartRecruitersScraper(BaseScraper):
    source = "smartrecruiters"

    async def fetch(self) -> AsyncIterator[RawJob]:
        base = f"https://api.smartrecruiters.com/v1/companies/{self.board}/postings"
        limit = 100
        max_pages = 10
        for page in range(max_pages):
            offset = page * limit
            list_url = f"{base}?offset={offset}&limit={limit}"
            resp = await self.client.get(list_url)
            resp.raise_for_status()
            data = resp.json()
            postings = data.get("content", []) or []
            if not postings:
                break
            for p in postings:
                posting_id = str(p.get("id", ""))
                detail_url = f"{base}/{posting_id}"
                try:
                    detail_resp = await self.client.get(detail_url)
                    detail_resp.raise_for_status()
                    detail = detail_resp.json()
                except Exception:  # noqa: BLE001
                    detail = {}
                sections = (detail.get("jobAd") or {}).get("sections") or {}
                parts = [
                    (sections.get("jobDescription") or {}).get("text") or "",
                    (sections.get("qualifications") or {}).get("text") or "",
                    (sections.get("responsibilities") or {}).get("text") or "",
                ]
                html = "\n".join(part for part in parts if part)
                description = (
                    BeautifulSoup(html, "lxml").get_text("\n", strip=True) if html else ""
                )
                posted_at: datetime | None = None
                if released := p.get("releasedDate"):
                    try:
                        posted_at = dateparser.isoparse(released)
                    except (ValueError, TypeError):
                        posted_at = None
                loc = p.get("location") or {}
                location = ", ".join(
                    v for v in [loc.get("city"), loc.get("country")] if v
                )
                url = p.get("ref") or f"https://jobs.smartrecruiters.com/{self.board}/{posting_id}"
                yield RawJob(
                    source=self.source,
                    source_id=posting_id,
                    url=url,
                    company=self.board.replace("-", " ").title(),
                    title=(p.get("name") or "").strip(),
                    location=location.strip(),
                    description=description,
                    posted_at=posted_at,
                    extra={
                        "industry": (p.get("industry") or {}).get("label"),
                        "department": (p.get("department") or {}).get("label"),
                    },
                )
            if len(postings) < limit:
                break
