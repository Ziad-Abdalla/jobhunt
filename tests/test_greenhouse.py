import httpx
import pytest
import respx

from jobhunt.scrapers.greenhouse import GreenhouseScraper


@pytest.mark.asyncio
@respx.mock
async def test_greenhouse_scraper_parses_payload():
    payload = {
        "jobs": [
            {
                "id": 12345,
                "title": "Backend Engineer",
                "absolute_url": "https://boards.greenhouse.io/acme/jobs/12345",
                "updated_at": "2026-05-20T10:00:00+00:00",
                "location": {"name": "Remote, US"},
                "offices": [{"name": "Remote"}],
                "departments": [{"name": "Engineering"}],
                "content": "<p>We use <b>Python</b> and Postgres. 3+ years.</p>",
            }
        ]
    }
    respx.get("https://boards-api.greenhouse.io/v1/boards/acme/jobs?content=true").mock(
        return_value=httpx.Response(200, json=payload)
    )

    async with httpx.AsyncClient() as client:
        scraper = GreenhouseScraper(client=client, board="acme")
        jobs = [j async for j in scraper.fetch()]

    assert len(jobs) == 1
    j = jobs[0]
    assert j.title == "Backend Engineer"
    assert j.source == "greenhouse"
    assert j.url.endswith("/12345")
    assert "Python" in j.description
    assert j.posted_at is not None
