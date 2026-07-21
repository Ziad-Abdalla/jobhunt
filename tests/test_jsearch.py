"""P8: JSearch (RapidAPI) adapter — parses the documented response shape.

Offline test only; the live probe is gated on the owner's throwaway key
(build-the-offline-code, defer-the-live-run).
"""

import asyncio

import httpx
import pytest
import respx

from jobhunt.config import settings
from jobhunt.scrapers import jsearch as jsearch_mod
from jobhunt.scrapers.jsearch import JSearchScraper, _parse_board

# Shape per a real /search-v2 response captured 2026-07-21 (v1 /search was
# retired upstream): results wrapped as data.jobs + cursor, singular
# job_employment_type is localized display text, the stable enum lives in
# job_employment_types, and job_salary_currency is gone.
_PAYLOAD = {
    "status": "OK",
    "request_id": "abc",
    "parameters": {"query": "developer", "country": "eg"},
    "data": {
        "cursor": "EqIECuIDQ",
        "jobs": [
            {
                "job_id": "eyJ1",
                "employer_name": "Instabug",
                "job_title": "Backend Engineer",
                "job_apply_link": "https://instabug.com/careers/backend",
                "job_description": "We use Python and Django in Cairo.",
                "job_city": "Cairo",
                "job_country": "EG",
                "job_employment_type": "دوام كامل",
                "job_employment_types": ["FULLTIME"],
                "job_is_remote": False,
                "job_posted_at_datetime_utc": "2026-07-15T00:00:00.000Z",
                "job_min_salary": 30000,
                "job_max_salary": 50000,
                "job_publisher": "Wuzzuf",
            },
            {
                "job_id": "eyJ2",
                "employer_name": "Remote Co",
                "job_title": "Frontend Engineer",
                "job_apply_link": "https://remote.co/j/2",
                "job_description": "React role.",
                "job_city": None,
                "job_country": None,
                "job_location": "Anywhere     •  عبر BeBee",
                "job_employment_types": ["CONTRACTOR"],
                "job_is_remote": True,
                "job_posted_at_datetime_utc": "2026-07-14T00:00:00.000Z",
            },
        ],
    },
}


@pytest.fixture(autouse=True)
def _key(monkeypatch):
    monkeypatch.setattr(settings, "jsearch_api_key", "TESTKEY")
    # Zero the live-API pacing so tests don't sleep.
    monkeypatch.setattr(jsearch_mod, "_MIN_INTERVAL", 0.0)
    monkeypatch.setattr(jsearch_mod, "_RETRY_DELAY", 0.0)
    monkeypatch.setattr(jsearch_mod, "_last_request", 0.0)


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
    route = respx.get("https://jsearch.p.rapidapi.com/search-v2").mock(
        return_value=httpx.Response(200, json=_PAYLOAD)
    )
    async with httpx.AsyncClient() as client:
        jobs = [j async for j in JSearchScraper(client=client, board="developer|Egypt").fetch()]

    # Auth headers were sent; a resolvable location becomes the country param.
    req = route.calls[0].request
    assert req.headers["x-rapidapi-key"] == "TESTKEY"
    assert req.headers["x-rapidapi-host"] == "jsearch.p.rapidapi.com"
    assert "country=eg" in str(req.url)
    assert "language=en" in str(req.url)
    assert "in+Egypt" not in str(req.url)

    assert len(jobs) == 2
    a = jobs[0]
    assert a.source == "jsearch"
    assert a.source_id == "eyJ1"
    assert a.company == "Instabug"
    assert a.title == "Backend Engineer"
    assert a.location == "Cairo, EG"
    # Enum list, never the localized display text ("دوام كامل").
    assert a.employment_type == "fulltime"   # → refresh map normalizes to Full-time
    assert a.remote_structured == ""
    assert a.salary_min == 30000 and a.salary_max == 50000 and a.salary_currency == ""
    assert a.posted_at is not None

    b = jobs[1]
    assert b.remote_structured == "remote"
    assert b.employment_type == "contractor"  # → Contract
    assert b.location == "Anywhere"           # job_location fallback, "via" tail cut


@pytest.mark.asyncio
@respx.mock
async def test_remote_only_param():
    route = respx.get("https://jsearch.p.rapidapi.com/search-v2").mock(
        return_value=httpx.Response(200, json={"status": "OK", "data": {"jobs": []}})
    )
    async with httpx.AsyncClient() as client:
        [j async for j in JSearchScraper(client=client, board="dev|remote").fetch()]
    url = str(route.calls[0].request.url)
    assert "work_from_home=true" in url
    assert "country=" not in url


@pytest.mark.asyncio
@respx.mock
async def test_unresolved_location_stays_in_query():
    route = respx.get("https://jsearch.p.rapidapi.com/search-v2").mock(
        return_value=httpx.Response(200, json={"status": "OK", "data": {"jobs": []}})
    )
    async with httpx.AsyncClient() as client:
        [j async for j in JSearchScraper(client=client, board="designer|Cairo").fetch()]
    url = str(route.calls[0].request.url)
    assert "designer+in+Cairo" in url or "designer%20in%20Cairo" in url
    assert "country=" not in url


@pytest.mark.asyncio
async def test_no_key_yields_nothing(monkeypatch):
    monkeypatch.setattr(settings, "jsearch_api_key", "")
    async with httpx.AsyncClient() as client:
        jobs = [j async for j in JSearchScraper(client=client, board="dev|Egypt").fetch()]
    assert jobs == []


@pytest.mark.asyncio
@respx.mock
async def test_concurrent_boards_never_overlap_requests():
    """scrape_all runs boards concurrently; the free tier rate-limits per
    second, so the adapter must serialize its own requests."""
    active = 0
    max_active = 0

    async def side(request):
        nonlocal active, max_active
        active += 1
        max_active = max(max_active, active)
        await asyncio.sleep(0.02)
        active -= 1
        return httpx.Response(200, json={"status": "OK", "data": []})

    respx.get("https://jsearch.p.rapidapi.com/search-v2").mock(side_effect=side)

    async def consume(board):
        return [j async for j in JSearchScraper(client=client, board=board).fetch()]

    async with httpx.AsyncClient() as client:
        await asyncio.gather(*(consume(b) for b in ("a|Egypt", "b|Egypt", "c|remote")))
    assert max_active == 1


@pytest.mark.asyncio
@respx.mock
async def test_retries_once_on_429():
    route = respx.get("https://jsearch.p.rapidapi.com/search-v2").mock(
        side_effect=[
            httpx.Response(429, json={"message": "Too many requests"}),
            httpx.Response(200, json=_PAYLOAD),
        ]
    )
    async with httpx.AsyncClient() as client:
        jobs = [j async for j in JSearchScraper(client=client, board="dev|Egypt").fetch()]
    assert route.call_count == 2
    assert len(jobs) == 2


@pytest.mark.asyncio
@respx.mock
async def test_second_429_raises():
    respx.get("https://jsearch.p.rapidapi.com/search-v2").mock(
        return_value=httpx.Response(429, json={"message": "Too many requests"})
    )
    with pytest.raises(httpx.HTTPStatusError):
        async with httpx.AsyncClient() as client:
            [j async for j in JSearchScraper(client=client, board="dev|Egypt").fetch()]


@pytest.mark.asyncio
@respx.mock
async def test_skips_entries_missing_url_or_title():
    payload = {"status": "OK", "data": [
        {"job_id": "x", "job_title": "No URL", "job_apply_link": ""},
        {"job_id": "y", "job_apply_link": "https://x.com/1", "job_title": ""},
    ]}
    respx.get("https://jsearch.p.rapidapi.com/search-v2").mock(
        return_value=httpx.Response(200, json=payload)
    )
    async with httpx.AsyncClient() as client:
        jobs = [j async for j in JSearchScraper(client=client, board="dev").fetch()]
    assert jobs == []
