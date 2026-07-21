"""Reddit hiring-thread adapter (old.reddit Atom RSS).

Only entries whose title carries a [Hiring]/(Hiring) marker are jobs;
[For Hire] posts are job SEEKERS and everything unmarked is discussion
noise (live-probed r/forhire + r/RemoteJobs, 2026-07-21)."""

from __future__ import annotations

import httpx
import pytest
import respx

import jobhunt.scrapers.reddit as reddit_mod
from jobhunt.scrapers.reddit import RedditScraper


@pytest.fixture(autouse=True)
def _no_throttle_bleed():
    """Reset the module-global spacing clock so the 15s inter-request gap
    never applies across tests."""
    reddit_mod._last_request = 0.0
    yield
    reddit_mod._last_request = 0.0


_FEED = """<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom">
  <category term="forhire" label="r/forhire"/>
  <entry>
    <author><name>/u/poster1</name></author>
    <id>t3_abc123</id>
    <link href="https://old.reddit.com/r/forhire/comments/abc123/hiring_dev/"/>
    <updated>2026-07-21T14:19:13+00:00</updated>
    <title>[Hiring] Python Developer for RAG pipeline - Remote - $40/hr</title>
    <content type="html">&lt;p&gt;Need a &lt;b&gt;Python&lt;/b&gt; dev for LLMs.&lt;/p&gt;</content>
  </entry>
  <entry>
    <author><name>/u/seeker</name></author>
    <id>t3_def456</id>
    <link href="https://old.reddit.com/r/forhire/comments/def456/for_hire_designer/"/>
    <updated>2026-07-21T14:00:00+00:00</updated>
    <title>[For Hire] Graphic Designer looking for work</title>
    <content type="html">I design things.</content>
  </entry>
  <entry>
    <author><name>/u/chatter</name></author>
    <id>t3_ghi789</id>
    <link href="https://old.reddit.com/r/forhire/comments/ghi789/question/"/>
    <updated>2026-07-21T13:00:00+00:00</updated>
    <title>How do I find clients here?</title>
    <content type="html">Just asking.</content>
  </entry>
  <entry>
    <author><name>/u/poster2</name></author>
    <id>t3_jkl012</id>
    <link href="https://old.reddit.com/r/forhire/comments/jkl012/hiring_editor/"/>
    <updated>2026-07-21T12:00:00+00:00</updated>
    <title>(HIRING) Video editor, ongoing work</title>
    <content type="html">Weekly videos.</content>
  </entry>
</feed>"""


@pytest.mark.asyncio
@respx.mock
async def test_reddit_parses_only_hiring_entries():
    respx.get("https://old.reddit.com/r/forhire/new/.rss").mock(
        return_value=httpx.Response(200, text=_FEED)
    )
    async with httpx.AsyncClient() as client:
        scraper = RedditScraper(client=client, board="forhire")
        jobs = [j async for j in scraper.fetch()]

    assert len(jobs) == 2
    first, second = jobs
    assert first.source == "reddit"
    assert first.title == "Python Developer for RAG pipeline - Remote - $40/hr"
    assert first.company == "r/forhire"
    assert first.url == "https://old.reddit.com/r/forhire/comments/abc123/hiring_dev/"
    assert first.source_id == "t3_abc123"
    assert first.posted_at is not None
    assert "Python" in first.description
    assert "<b>" not in first.description  # HTML stripped
    assert second.title == "Video editor, ongoing work"


@pytest.mark.asyncio
@respx.mock
async def test_reddit_retries_once_on_429(monkeypatch):
    monkeypatch.setattr(reddit_mod, "_RETRY_DELAY", 0.0)
    route = respx.get("https://old.reddit.com/r/jobbit/new/.rss")
    route.side_effect = [
        httpx.Response(429),
        httpx.Response(200, text=_FEED),
    ]
    async with httpx.AsyncClient() as client:
        scraper = RedditScraper(client=client, board="jobbit")
        jobs = [j async for j in scraper.fetch()]
    assert len(jobs) == 2
    assert route.call_count == 2


@pytest.mark.asyncio
@respx.mock
async def test_reddit_empty_board_yields_nothing():
    async with httpx.AsyncClient() as client:
        scraper = RedditScraper(client=client, board="")
        jobs = [j async for j in scraper.fetch()]
    assert jobs == []
