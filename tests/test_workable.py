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


@pytest.mark.asyncio
@respx.mock
async def test_workable_v1_fallback_when_v3_missing():
    """Some accounts (e.g. huggingface, live-probed 2026-07-21) 404 on the v3
    widget API but publish via the older v1 accounts API — fall back to it."""
    v1_payload = {
        "name": "Hugging Face",
        "jobs": [
            {
                "title": "ML Engineer, Open Source",
                "shortcode": "97904BAC90",
                "employment_type": "Full-time",
                "telecommuting": True,
                "department": "Product",
                "url": "https://apply.workable.com/j/97904BAC90",
                "published_on": "2026-05-29",
                "created_at": "2026-05-29",
                "country": "France",
                "city": "Paris",
                "state": "Île-de-France",
                "description": "<p>Work on <strong>transformers</strong>.</p>",
            }
        ],
    }
    respx.get(
        "https://apply.workable.com/api/v3/accounts/huggingface/jobs"
    ).mock(return_value=httpx.Response(404))
    respx.get(
        "https://apply.workable.com/api/v1/widget/accounts/huggingface",
        params={"details": "true"},
    ).mock(return_value=httpx.Response(200, json=v1_payload))

    async with httpx.AsyncClient() as client:
        scraper = WorkableScraper(client=client, board="huggingface")
        jobs = [j async for j in scraper.fetch()]

    assert len(jobs) == 1
    job = jobs[0]
    assert job.source == "workable"
    assert job.title == "ML Engineer, Open Source"
    assert job.url == "https://apply.workable.com/j/97904BAC90"
    assert job.source_id == "97904BAC90"
    assert "Paris" in job.location and "France" in job.location
    assert "transformers" in job.description
    assert "<strong>" not in job.description
    assert job.employment_type == "Full-time"
    assert job.posted_at is not None


@pytest.mark.asyncio
@respx.mock
async def test_workable_v3_404_and_v1_404_raises():
    """A genuinely missing account still surfaces as an error (doctor visibility)."""
    respx.get(
        "https://apply.workable.com/api/v3/accounts/ghost/jobs"
    ).mock(return_value=httpx.Response(404))
    respx.get(
        "https://apply.workable.com/api/v1/widget/accounts/ghost",
        params={"details": "true"},
    ).mock(return_value=httpx.Response(404))

    async with httpx.AsyncClient() as client:
        scraper = WorkableScraper(client=client, board="ghost")
        with pytest.raises(httpx.HTTPStatusError):
            _ = [j async for j in scraper.fetch()]
