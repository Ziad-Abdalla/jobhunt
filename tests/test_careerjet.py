"""Careerjet public affiliate API adapter — parses the documented shape.

Offline tests only (jsearch precedent: build-the-offline-code,
defer-the-live-run). The endpoint 403s without a valid affid, so the live
`jobhunt doctor` probe is gated on the owner opening a free Careerjet
partner account and pasting the affid on the Settings page.
"""

import httpx
import pytest
import respx

from jobhunt.config import settings
from jobhunt.scrapers.careerjet import CareerjetScraper, _parse_board

# Shape per the official careerjet-api-client docs: type=JOBS, jobs list
# with title/company/locations/salary/date/description/url/site.
_PAYLOAD = {
    "type": "JOBS",
    "hits": 2,
    "pages": 1,
    "response_time": 0.1,
    "jobs": [
        {
            "title": "Python Developer",
            "company": "Acme Egypt",
            "locations": "Cairo, Egypt",
            "salary": "EGP 30,000 per month",
            "date": "2026-07-15 00:00:00",
            "description": "Build APIs with Django in Cairo.",
            "url": "https://jobviewtrack.com/en-eg/job-1234/abc.html",
            "site": "wuzzuf.net",
        },
        {
            "title": "ML Engineer",
            "company": "",
            "locations": "Remote",
            "salary": "",
            "date": "2026-07-14 00:00:00",
            "description": "LLM fine-tuning role.",
            "url": "https://jobviewtrack.com/en-eg/job-5678/def.html",
            "site": "bayt.com",
        },
    ],
}


def test_parse_board_splits_query_and_location():
    assert _parse_board("python developer|Egypt") == ("python developer", "Egypt")
    assert _parse_board("python developer") == ("python developer", "")
    assert _parse_board("  ai engineer | Cairo ") == ("ai engineer", "Cairo")


@pytest.mark.asyncio
@respx.mock
async def test_careerjet_parses_payload(monkeypatch):
    monkeypatch.setattr(settings, "careerjet_affid", "testaffid123")
    route = respx.get("http://public.api.careerjet.net/search").mock(
        return_value=httpx.Response(200, json=_PAYLOAD)
    )
    async with httpx.AsyncClient() as client:
        scraper = CareerjetScraper(client=client, board="python developer|Egypt")
        jobs = [j async for j in scraper.fetch()]

    assert len(jobs) == 2
    first, second = jobs
    assert first.source == "careerjet"
    assert first.title == "Python Developer"
    assert first.company == "Acme Egypt"
    assert first.location == "Cairo, Egypt"
    assert "Django" in first.description
    assert first.posted_at is not None
    assert first.url.startswith("https://jobviewtrack.com")
    assert second.title == "ML Engineer"

    # Request carried the affid + Egypt locale resolved from the location.
    params = dict(route.calls[0].request.url.params)
    assert params["affid"] == "testaffid123"
    assert params["locale_code"] == "en_EG"
    assert params["keywords"] == "python developer"


@pytest.mark.asyncio
@respx.mock
async def test_careerjet_unknown_location_falls_back_to_location_param(monkeypatch):
    monkeypatch.setattr(settings, "careerjet_affid", "testaffid123")
    route = respx.get("http://public.api.careerjet.net/search").mock(
        return_value=httpx.Response(200, json={"type": "JOBS", "hits": 0, "pages": 0, "jobs": []})
    )
    async with httpx.AsyncClient() as client:
        scraper = CareerjetScraper(client=client, board="developer|Atlantis City")
        _ = [j async for j in scraper.fetch()]
    params = dict(route.calls[0].request.url.params)
    assert params["locale_code"] == "en_GB"  # default locale
    assert params["location"] == "Atlantis City"


@pytest.mark.asyncio
@respx.mock
async def test_careerjet_known_city_keeps_location_and_locale(monkeypatch):
    """'…|Cairo' must search Cairo within the Egypt index — a bare locale
    would silently widen it to all of Egypt."""
    monkeypatch.setattr(settings, "careerjet_affid", "testaffid123")
    route = respx.get("http://public.api.careerjet.net/search").mock(
        return_value=httpx.Response(200, json={"type": "JOBS", "hits": 0, "pages": 0, "jobs": []})
    )
    async with httpx.AsyncClient() as client:
        scraper = CareerjetScraper(client=client, board="developer|Cairo")
        _ = [j async for j in scraper.fetch()]
    params = dict(route.calls[0].request.url.params)
    assert params["locale_code"] == "en_EG"
    assert params["location"] == "Cairo"


@pytest.mark.asyncio
async def test_careerjet_no_affid_yields_nothing(monkeypatch):
    monkeypatch.setattr(settings, "careerjet_affid", "")
    async with httpx.AsyncClient() as client:
        scraper = CareerjetScraper(client=client, board="developer|Egypt")
        jobs = [j async for j in scraper.fetch()]
    assert jobs == []


@pytest.mark.asyncio
@respx.mock
async def test_careerjet_error_type_yields_nothing(monkeypatch):
    monkeypatch.setattr(settings, "careerjet_affid", "testaffid123")
    respx.get("http://public.api.careerjet.net/search").mock(
        return_value=httpx.Response(200, json={"type": "ERROR", "error": "bad affid"})
    )
    async with httpx.AsyncClient() as client:
        scraper = CareerjetScraper(client=client, board="developer|Egypt")
        jobs = [j async for j in scraper.fetch()]
    assert jobs == []
