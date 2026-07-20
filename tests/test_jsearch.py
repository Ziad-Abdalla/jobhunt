"""P8: JSearch (RapidAPI) adapter — parses the documented response shape.

Offline test only; the live probe is gated on the owner's throwaway key
(build-the-offline-code, defer-the-live-run).
"""

import httpx
import pytest
import respx

from jobhunt.config import settings
from jobhunt.scrapers.jsearch import JSearchScraper, _parse_board

# Shape per https://rapidapi.com/letscrape-6bRBa3QguO5/api/jsearch (search).
_PAYLOAD = {
    "status": "OK",
    "request_id": "abc",
    "data": [
        {
            "job_id": "eyJ1",
            "employer_name": "Instabug",
            "job_title": "Backend Engineer",
            "job_apply_link": "https://instabug.com/careers/backend",
            "job_description": "We use Python and Django in Cairo.",
            "job_city": "Cairo",
            "job_country": "EG",
            "job_employment_type": "FULLTIME",
            "job_is_remote": False,
            "job_posted_at_datetime_utc": "2026-07-15T00:00:00.000Z",
            "job_min_salary": 30000,
            "job_max_salary": 50000,
            "job_salary_currency": "USD",
            "job_publisher": "Wuzzuf",
        },
        {
            "job_id": "eyJ2",
            "employer_name": "Remote Co",
            "job_title": "Frontend Engineer",
            "job_apply_link": "https://remote.co/j/2",
            "job_description": "React role.",
            "job_city": "",
            "job_country": "",
            "job_employment_type": "CONTRACTOR",
            "job_is_remote": True,
            "job_posted_at_datetime_utc": "2026-07-14T00:00:00.000Z",
        },
    ],
}


@pytest.fixture(autouse=True)
def _key(monkeypatch):
    monkeypatch.setattr(settings, "jsearch_api_key", "TESTKEY")


class TestParseBoard:
    def test_query_location(self):
        assert _parse_board("developer|Egypt") == ("developer", "Egypt", False)

    def test_query_only(self):
        assert _parse_board("developer") == ("developer", "", False)

    def test_remote_marker(self):
        assert _parse_board("developer|remote") == ("developer", "", True)


@pytest.mark.asyncio
@respx.mock
async def test_parses_payload():
    route = respx.get("https://jsearch.p.rapidapi.com/search").mock(
        return_value=httpx.Response(200, json=_PAYLOAD)
    )
    async with httpx.AsyncClient() as client:
        jobs = [j async for j in JSearchScraper(client=client, board="developer|Egypt").fetch()]

    # Auth headers + query were sent.
    req = route.calls[0].request
    assert req.headers["x-rapidapi-key"] == "TESTKEY"
    assert req.headers["x-rapidapi-host"] == "jsearch.p.rapidapi.com"
    assert "developer+in+Egypt" in str(req.url) or "developer%20in%20Egypt" in str(req.url)

    assert len(jobs) == 2
    a = jobs[0]
    assert a.source == "jsearch"
    assert a.source_id == "eyJ1"
    assert a.company == "Instabug"
    assert a.title == "Backend Engineer"
    assert a.location == "Cairo, EG"
    assert a.employment_type == "fulltime"   # → refresh map normalizes to Full-time
    assert a.remote_structured == ""
    assert a.salary_min == 30000 and a.salary_max == 50000 and a.salary_currency == "USD"
    assert a.posted_at is not None

    b = jobs[1]
    assert b.remote_structured == "remote"
    assert b.employment_type == "contractor"  # → Contract


@pytest.mark.asyncio
@respx.mock
async def test_remote_only_param():
    route = respx.get("https://jsearch.p.rapidapi.com/search").mock(
        return_value=httpx.Response(200, json={"status": "OK", "data": []})
    )
    async with httpx.AsyncClient() as client:
        [j async for j in JSearchScraper(client=client, board="dev|remote").fetch()]
    assert "remote_jobs_only=true" in str(route.calls[0].request.url)


@pytest.mark.asyncio
async def test_no_key_yields_nothing(monkeypatch):
    monkeypatch.setattr(settings, "jsearch_api_key", "")
    async with httpx.AsyncClient() as client:
        jobs = [j async for j in JSearchScraper(client=client, board="dev|Egypt").fetch()]
    assert jobs == []


@pytest.mark.asyncio
@respx.mock
async def test_skips_entries_missing_url_or_title():
    payload = {"status": "OK", "data": [
        {"job_id": "x", "job_title": "No URL", "job_apply_link": ""},
        {"job_id": "y", "job_apply_link": "https://x.com/1", "job_title": ""},
    ]}
    respx.get("https://jsearch.p.rapidapi.com/search").mock(
        return_value=httpx.Response(200, json=payload)
    )
    async with httpx.AsyncClient() as client:
        jobs = [j async for j in JSearchScraper(client=client, board="dev").fetch()]
    assert jobs == []
