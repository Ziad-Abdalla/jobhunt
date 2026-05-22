import httpx
import pytest
import respx

from jobhunt.scrapers.workable import WorkableScraper


@pytest.mark.asyncio
@respx.mock
async def test_workable_scraper_parses_payload():
    payload = {
        "jobs": [
            {
                "shortcode": "ABC123",
                "title": "Platform Engineer",
                "url": "https://apply.workable.com/acme/j/ABC123",
                "shortlink": "https://workable.com/nr/ABC123",
                "created_at": "2026-05-21T09:30:00Z",
                "location": {
                    "city": "London",
                    "region": "England",
                    "country": "United Kingdom",
                },
                "department": "Engineering",
                "employment_type": "Full-time",
                "description": "<p>Build <strong>distributed</strong> systems in Go.</p>",
            },
            {
                "shortcode": "XYZ999",
                "title": "Data Scientist",
                "url": "https://apply.workable.com/acme/j/XYZ999",
                "created_at": "2026-05-19T12:00:00Z",
                "location": {"city": "Remote", "country": "EU"},
                "department": "Data",
                "employment_type": "Full-time",
                "description": "",
            },
        ],
        "paging": {"next": None},
    }
    detail_payload = {
        "shortcode": "XYZ999",
        "description": "<div>Work with <em>PyTorch</em> on ranking models.</div>",
    }
    respx.get(
        "https://apply.workable.com/api/v3/accounts/acme/jobs"
    ).mock(return_value=httpx.Response(200, json=payload))
    respx.get(
        "https://apply.workable.com/api/v3/accounts/acme/jobs/XYZ999"
    ).mock(return_value=httpx.Response(200, json=detail_payload))

    async with httpx.AsyncClient() as client:
        scraper = WorkableScraper(client=client, board="acme")
        jobs = [j async for j in scraper.fetch()]

    assert len(jobs) == 2
    first, second = jobs
    assert first.source == "workable"
    assert first.title == "Platform Engineer"
    assert first.url == "https://apply.workable.com/acme/j/ABC123"
    assert first.posted_at is not None
    assert "distributed" in first.description
    assert "<strong>" not in first.description  # BeautifulSoup ran
    assert "London" in first.location

    assert second.title == "Data Scientist"
    assert "PyTorch" in second.description
    assert "<em>" not in second.description
