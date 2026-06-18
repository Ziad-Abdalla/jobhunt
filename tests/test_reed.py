import httpx
import pytest
import respx

from jobhunt.config import settings
from jobhunt.scrapers.reed import ReedScraper

_RESULTS = {
    "results": [
        {
            "jobId": 99,
            "jobTitle": "Warehouse Operative",
            "employerName": "Acme Logistics",
            "locationName": "London",
            "jobUrl": "https://www.reed.co.uk/jobs/99",
            "date": "18/06/2026",
            "jobDescription": "<p>No experience needed. Weekend shifts.</p>",
            "employmentType": "Part time",
            "minimumSalary": 22000,
            "maximumSalary": 24000,
            "currency": "GBP",
        }
    ]
}


@pytest.mark.asyncio
@respx.mock
async def test_reed_scopes_search_to_user_location_and_radius(monkeypatch):
    """When the user has set a home location, every Reed search is scoped to
    that town + a travel radius (Reed filters by distance server-side)."""
    monkeypatch.setattr(settings, "reed_api_key", "testkey")
    monkeypatch.setattr(settings, "user_location", "London, UK")

    route = respx.get("https://www.reed.co.uk/api/1.0/search").mock(
        side_effect=[
            httpx.Response(200, json=_RESULTS),
            httpx.Response(200, json={"results": []}),
        ]
    )

    async with httpx.AsyncClient() as client:
        scraper = ReedScraper(client=client, board="warehouse")
        jobs = [j async for j in scraper.fetch()]

    params = route.calls.last.request.url.params
    assert params["keywords"] == "warehouse"
    # "London, UK" -> Reed wants just the town name "London".
    assert params["locationName"] == "London"
    # The travel radius (default 15 miles) is passed through to Reed.
    assert params["distanceFromLocation"] == "15"
    assert len(jobs) == 1
    assert jobs[0].location == "London"


@pytest.mark.asyncio
@respx.mock
async def test_reed_searches_uk_wide_when_no_home_location(monkeypatch):
    """With no home location set, Reed stays UK-wide (no location params)."""
    monkeypatch.setattr(settings, "reed_api_key", "testkey")
    monkeypatch.setattr(settings, "user_location", "")

    route = respx.get("https://www.reed.co.uk/api/1.0/search").mock(
        return_value=httpx.Response(200, json={"results": []})
    )

    async with httpx.AsyncClient() as client:
        scraper = ReedScraper(client=client, board="software engineer")
        _ = [j async for j in scraper.fetch()]

    params = route.calls.last.request.url.params
    assert "locationName" not in params
    assert "distanceFromLocation" not in params
