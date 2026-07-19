import httpx
import pytest
import respx

from jobhunt.scrapers.weworkremotely import WeWorkRemotelyScraper

_RSS = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0" xmlns:media="http://search.yahoo.com/mrss"><channel>
<title>We Work Remotely</title>
<item>
<media:content url="https://logo.gif" type="image/png"/>
<title>Globex: Senior Full-Stack Developer (Remote)</title>
<region>Anywhere in the World</region>
<category>Full-Stack Programming</category>
<description>&lt;p&gt;&lt;strong&gt;Headquarters:&lt;/strong&gt; Berlin&lt;/p&gt;&lt;p&gt;Build with React and Node.&lt;/p&gt;</description>
<pubDate>Tue, 30 Jun 2026 20:32:52 +0000</pubDate>
<guid>https://weworkremotely.com/remote-jobs/globex-senior-full-stack-developer</guid>
<link>https://weworkremotely.com/remote-jobs/globex-senior-full-stack-developer</link>
</item>
</channel></rss>"""


@pytest.mark.asyncio
@respx.mock
async def test_weworkremotely_parses_feed():
    respx.get("https://weworkremotely.com/categories/remote-programming-jobs.rss").mock(
        return_value=httpx.Response(200, text=_RSS)
    )
    async with httpx.AsyncClient() as client:
        scraper = WeWorkRemotelyScraper(client=client, board="remote-programming-jobs")
        jobs = [j async for j in scraper.fetch()]

    assert len(jobs) == 1
    j = jobs[0]
    assert j.source == "weworkremotely"
    # "Company: Role" — the company prefix is split off the title.
    assert j.company == "Globex"
    assert j.title == "Senior Full-Stack Developer (Remote)"
    assert j.url.endswith("globex-senior-full-stack-developer")
    assert j.remote_structured == "remote"  # WWR is remote-only
    assert j.location == "Anywhere in the World"
    assert "React" in j.description  # escaped HTML unwrapped to text
    assert j.posted_at is not None
