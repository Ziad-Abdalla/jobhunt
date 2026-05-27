"""Hacker News 'Who is Hiring?' monthly thread via the Algolia API.

We find the latest 'Ask HN: Who is hiring?' story, then iterate its top-level comments.
Each top-level comment is treated as one job posting. Company/title are best-effort
parsed from the first line; this is messier than ATS sources but is a useful firehose.
"""

from __future__ import annotations

import re
from collections.abc import AsyncIterator
from datetime import UTC, datetime

from bs4 import BeautifulSoup

from .base import BaseScraper, RawJob

_HEADER_SPLIT = re.compile(r"\s*[|–—-]\s*")  # split on | – — -


class HackerNewsScraper(BaseScraper):
    source = "hackernews"

    async def fetch(self) -> AsyncIterator[RawJob]:
        # 1. Find the most recent "Ask HN: Who is hiring" story.
        search = (
            "https://hn.algolia.com/api/v1/search_by_date"
            "?tags=story,author_whoishiring"
            "&query=who+is+hiring"
            "&hitsPerPage=5"
        )
        resp = await self.client.get(search)
        resp.raise_for_status()
        story = None
        for hit in resp.json().get("hits", []):
            t = (hit.get("title") or "").lower()
            if "who is hiring" in t and "ask hn" in t:
                story = hit
                break
        if not story:
            return

        story_id = story.get("objectID")
        story_url = f"https://news.ycombinator.com/item?id={story_id}"
        # 2. Fetch top-level comments of that story.
        item_url = f"https://hn.algolia.com/api/v1/items/{story_id}"
        item_resp = await self.client.get(item_url)
        item_resp.raise_for_status()
        item = item_resp.json()
        for child in item.get("children", []):
            text = child.get("text") or ""
            if not text or not child.get("author"):
                continue
            description = BeautifulSoup(text, "lxml").get_text("\n", strip=True)
            first_line = description.splitlines()[0] if description else ""
            parts = [p.strip() for p in _HEADER_SPLIT.split(first_line) if p.strip()]
            company = parts[0] if parts else (child.get("author") or "Unknown")
            title = " ".join(parts[1:3]) if len(parts) > 1 else "Software Engineer"
            location_match = re.search(
                r"\b(remote|hybrid|onsite|on[- ]site|[A-Z][a-z]+(?:,\s*[A-Z]{2,})?)\b",
                first_line,
            )
            location = location_match.group(0) if location_match else ""
            posted_at: datetime | None = None
            if ts := child.get("created_at_i"):
                try:
                    posted_at = datetime.fromtimestamp(int(ts), tz=UTC)
                except (ValueError, TypeError):
                    posted_at = None
            yield RawJob(
                source=self.source,
                source_id=str(child.get("id", "")),
                url=story_url + f"#{child.get('id')}",
                company=company[:128],
                title=title[:256] or "Software Engineer",
                location=location[:128],
                description=description,
                posted_at=posted_at,
                extra={"hn_story_id": story_id, "author": child.get("author")},
            )
