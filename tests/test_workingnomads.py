import httpx
import pytest
import respx

from jobhunt.scrapers.workingnomads import WorkingNomadsScraper

_PAYLOAD = [
    {
        "url": "https://www.workingnomads.com/job/go/1734670/",
        "title": "Senior AI Engineer",
        "description": "<p>Remote role building <b>ML</b> systems.</p>",
        "company_name": "Lemon.io",
        "category_name": "Development",
        "tags": "python,machine learning,architecture",
        "location": "Europe, North America, APAC",
        "pub_date": "2026-07-17T07:17:36-04:00",
    }
]


@pytest.mark.asyncio
@respx.mock
async def test_workingnomads_parses_payload():
    respx.get("https://www.workingnomads.com/api/exposed_jobs/").mock(
        return_value=httpx.Response(200, json=_PAYLOAD)
    )
    async with httpx.AsyncClient() as client:
        jobs = [j async for j in WorkingNomadsScraper(client=client, board="").fetch()]

    assert len(jobs) == 1
    j = jobs[0]
    assert j.source == "workingnomads"
    assert j.title == "Senior AI Engineer"
    assert j.company == "Lemon.io"
    assert j.url == "https://www.workingnomads.com/job/go/1734670/"
    assert j.source_id  # derived from the url when no id field exists
    assert j.remote_structured == "remote"  # Working Nomads is remote-only
    assert "ML" in j.description  # HTML stripped
    assert j.posted_at is not None
