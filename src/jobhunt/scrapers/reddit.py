"""Reddit hiring threads via old.reddit.com Atom RSS.

The board is a subreddit name (e.g. "forhire", "jobbit"). Only entries
whose title starts with a [Hiring]/(Hiring) marker are yielded — [For
Hire] posts are job SEEKERS and unmarked posts are discussion noise
(live-probed r/forhire + r/RemoteJobs 2026-07-21). Freelance/contract
lane: gigs, one-offs, small remote contracts.

Endpoint: https://old.reddit.com/r/{sub}/new/.rss — the JSON endpoints
(www + old, /new.json) are 403-blocked for scripted clients since the
2023 API changes; the RSS feed is the remaining public path and it
rate-limits hard (a 15s spacing still drew a 429 on the third board in
the first live doctor pass), so requests are serialized ~30s apart with
one retry after a 429. Keep the board count low (2-3 subreddits).
"""

from __future__ import annotations

import asyncio
import re
import time
from collections.abc import AsyncIterator
from datetime import datetime

import httpx
from bs4 import BeautifulSoup
from dateutil import parser as dateparser

from .base import BaseScraper, RawJob

# Title must OPEN with a hiring marker: [Hiring], (HIRING), [hiring] ...
_HIRING_RE = re.compile(r"^\s*[\[(]\s*hiring\s*[\])]\s*:?\s*", re.IGNORECASE)

_MIN_INTERVAL = 30.0
_RETRY_DELAY = 60.0
_last_request = 0.0

# One lock per running event loop (same pattern as the jsearch throttle):
# an asyncio.Lock binds to the loop it is first used on.
_locks: dict[int, asyncio.Lock] = {}


def _loop_lock() -> asyncio.Lock:
    key = id(asyncio.get_running_loop())
    if key not in _locks:
        _locks.clear()
        _locks[key] = asyncio.Lock()
    return _locks[key]


async def _spaced_get(client: httpx.AsyncClient, url: str) -> httpx.Response:
    global _last_request
    async with _loop_lock():
        wait = _last_request + _MIN_INTERVAL - time.monotonic()
        if wait > 0:
            await asyncio.sleep(wait)
        resp = await client.get(url)
        if resp.status_code == 429:
            await asyncio.sleep(_RETRY_DELAY)
            resp = await client.get(url)
        _last_request = time.monotonic()
    return resp


class RedditScraper(BaseScraper):
    source = "reddit"

    async def fetch(self) -> AsyncIterator[RawJob]:
        sub = (self.board or "").strip().strip("/")
        if not sub:
            return
        url = f"https://old.reddit.com/r/{sub}/new/.rss"
        resp = await _spaced_get(self.client, url)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "xml")

        for entry in soup.find_all("entry"):
            raw_title = (entry.find("title").text or "").strip() if entry.find("title") else ""
            m = _HIRING_RE.match(raw_title)
            if not m:
                continue
            title = raw_title[m.end():].strip() or raw_title

            link_el = entry.find("link")
            link = (link_el.get("href") or "").strip() if link_el is not None else ""
            if not link:
                continue

            content_el = entry.find("content")
            description = (
                BeautifulSoup(content_el.text or "", "lxml").get_text("\n", strip=True)
                if content_el is not None
                else ""
            )

            posted_at: datetime | None = None
            updated_el = entry.find("updated")
            if updated_el is not None and updated_el.text:
                try:
                    posted_at = dateparser.parse(updated_el.text)
                except (ValueError, TypeError, OverflowError):
                    posted_at = None

            id_el = entry.find("id")
            author_el = entry.find("name")
            yield RawJob(
                source=self.source,
                source_id=(id_el.text or "").strip() if id_el is not None else link,
                url=link,
                # Posts carry no employer name; the honest label is the sub.
                company=f"r/{sub}",
                title=title[:256],
                location="",
                description=description,
                posted_at=posted_at,
                extra={"author": (author_el.text or "").strip() if author_el is not None else ""},
            )
