import httpx
import pytest
import respx

from jobhunt.scrapers.wuzzuf import WuzzufScraper

_RSS = """<?xml version="1.0" encoding="UTF-8" ?>
<rss version="2.0"><channel>
<title>WUZZUF All Jobs</title>
<item>
<title><![CDATA[Junior Backend Developer]]></title>
<link><![CDATA[https://wuzzuf.net/jobs/p/abc-Junior-Backend-Developer-Acme-Cairo-Egypt]]></link>
<guid isPermaLink="true"><![CDATA[https://wuzzuf.net/jobs/p/abc123]]></guid>
<pubDate><![CDATA[Mon, 06 Jul 2026 15:08:56 GMT]]></pubDate>
<source url="https://wuzzuf.net/jobs/careers/acme"><![CDATA[Acme]]></source>
<description><![CDATA[Build and maintain APIs in Python and Django.]]></description>
<salary><![CDATA[Salary: Negotiable]]></salary>
<experience><![CDATA[1-3 years]]></experience>
<roles><![CDATA[IT/Software Development]]></roles>
<career_level><![CDATA[Entry Level]]></career_level>
<job_requirements><![CDATA[BSc in Computer Science. Strong Python.]]></job_requirements>
<job_type><![CDATA[Full Time]]></job_type>
<area><![CDATA[Cairo]]></area>
</item>
</channel></rss>"""


@pytest.mark.asyncio
@respx.mock
async def test_wuzzuf_parses_egypt_feed():
    respx.get("https://wuzzuf.net/feeds/all-jobs.xml").mock(
        return_value=httpx.Response(200, text=_RSS)
    )
    async with httpx.AsyncClient() as client:
        jobs = [j async for j in WuzzufScraper(client=client, board="").fetch()]

    assert len(jobs) == 1
    j = jobs[0]
    assert j.source == "wuzzuf"
    assert j.title == "Junior Backend Developer"
    assert j.company == "Acme"
    assert j.url.startswith("https://wuzzuf.net/jobs/p/")
    assert j.source_id == "https://wuzzuf.net/jobs/p/abc123"
    # Wuzzuf is Egypt-only; location must carry Egypt so the Egypt filter/region map hits.
    assert "Egypt" in j.location
    assert "Cairo" in j.location
    assert "Python" in j.description
    assert "BSc" in j.description  # requirements folded into the description
    assert j.employment_type == "Full Time"  # raw value; refresh normalizes to Full-time
    assert j.posted_at is not None
