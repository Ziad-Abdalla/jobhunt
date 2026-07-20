"""Wuzzuf structured-metadata mapping (P3).

Wuzzuf's feed states career_level / experience / job_type outright — structured
metadata beats regex guessing, especially for Arabic-language postings.
"""

from __future__ import annotations

import httpx
import pytest
import respx

from jobhunt.scrapers.wuzzuf import (
    WuzzufScraper,
    _map_career_level,
    _parse_experience_years,
)

_FEED = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0"><channel>
  <item>
    <title>Accountant</title>
    <link>https://wuzzuf.net/jobs/p/1</link>
    <guid>wz-1</guid>
    <source>Acme Egypt</source>
    <area>Cairo</area>
    <description>Great role</description>
    <career_level>Entry Level</career_level>
    <experience>1-3 Yrs of Exp</experience>
    <job_type>Full Time</job_type>
    <pubDate>Sun, 19 Jul 2026 10:00:00 GMT</pubDate>
  </item>
</channel></rss>"""


class TestCareerLevelMap:
    @pytest.mark.parametrize("raw,expected", [
        ("Student", "intern"),
        ("Entry Level", "entry"),
        ("Experienced (Non-Manager)", "mid"),
        ("Manager", "lead"),
        ("Senior Management (e.g. VP, CEO)", "senior"),
        ("Something Unrecognized", ""),
        ("", ""),
    ])
    def test_map(self, raw, expected):
        assert _map_career_level(raw) == expected


class TestExperienceParse:
    @pytest.mark.parametrize("raw,expected", [
        ("1-3 Yrs of Exp", 1),
        ("5+ Yrs of Exp", 5),
        ("1-3 years", 1),
        ("No Exp Required", None),
        ("", None),
    ])
    def test_parse(self, raw, expected):
        assert _parse_experience_years(raw) == expected


@pytest.mark.asyncio
@respx.mock
async def test_fetch_populates_structured_fields():
    respx.get("https://wuzzuf.net/feeds/all-jobs.xml").mock(
        return_value=httpx.Response(200, text=_FEED)
    )
    async with httpx.AsyncClient() as client:
        scraper = WuzzufScraper(client=client, board="")
        jobs = [j async for j in scraper.fetch()]
    assert len(jobs) == 1
    assert jobs[0].level_structured == "entry"
    assert jobs[0].min_years_structured == 1
    assert jobs[0].employment_type == "Full Time"
