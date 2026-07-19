import httpx
import pytest
import respx

from jobhunt.scrapers.pythonjobs import PythonJobsScraper

_RSS = """<?xml version="1.0"?><rss version="2.0"><channel>
<title>Python Job Board</title>
<item>
<title>Backend Engineer, Globex Ltd</title>
<link>https://www.python.org/jobs/8105/</link>
<description>Glasgow, Scotland, United Kingdom
&lt;p&gt;Build data pipelines in Python.&lt;/p&gt;</description>
<pubDate>Wed, 01 Jul 2026 10:00:00 GMT</pubDate>
<guid>https://www.python.org/jobs/8105/</guid>
</item>
</channel></rss>"""


@pytest.mark.asyncio
@respx.mock
async def test_pythonjobs_parses_feed():
    respx.get("https://www.python.org/jobs/feed/rss/").mock(
        return_value=httpx.Response(200, text=_RSS)
    )
    async with httpx.AsyncClient() as client:
        jobs = [j async for j in PythonJobsScraper(client=client, board="").fetch()]

    assert len(jobs) == 1
    j = jobs[0]
    assert j.source == "pythonjobs"
    # "Role, Company" — the trailing company is split off the title.
    assert j.title == "Backend Engineer"
    assert j.company == "Globex Ltd"
    assert j.url.endswith("/8105/")
    assert j.location.startswith("Glasgow")
    assert "Python" in j.description
    assert j.posted_at is not None
