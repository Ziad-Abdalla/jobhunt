import httpx
import pytest
import respx

from jobhunt.scrapers.workday import WorkdayScraper


@pytest.mark.asyncio
@respx.mock
async def test_workday_scraper_parses_payload():
    list_payload = {
        "jobPostings": [
            {
                "title": "Senior Backend Engineer",
                "externalPath": "/job/Remote-US/Senior-Backend-Engineer_R-12345",
                "locationsText": "Remote, US",
                "postedOn": "Posted 3 Days Ago",
                "bulletFields": ["R-12345"],
            }
        ]
    }
    detail_payload = {
        "jobPostingInfo": {
            "title": "Senior Backend Engineer",
            "jobDescription": "<p>Build distributed <b>Python</b> services.</p>",
        }
    }

    respx.post(
        "https://nvidia.wd5.myworkdayjobs.com/wday/cxs/nvidia/NVIDIAExternalCareerSite/jobs"
    ).mock(return_value=httpx.Response(200, json=list_payload))
    respx.get(
        "https://nvidia.wd5.myworkdayjobs.com/wday/cxs/nvidia/NVIDIAExternalCareerSite"
        "/job/Remote-US/Senior-Backend-Engineer_R-12345"
    ).mock(return_value=httpx.Response(200, json=detail_payload))

    async with httpx.AsyncClient() as client:
        scraper = WorkdayScraper(client=client, board="nvidia/NVIDIAExternalCareerSite")
        jobs = [j async for j in scraper.fetch()]

    assert len(jobs) == 1
    j = jobs[0]
    assert j.source == "workday"
    assert j.title == "Senior Backend Engineer"
    assert j.url == (
        "https://nvidia.wd5.myworkdayjobs.com/en-US/NVIDIAExternalCareerSite"
        "/job/Remote-US/Senior-Backend-Engineer_R-12345"
    )
    assert "Python" in j.description
    assert j.location == "Remote, US"
    assert j.posted_at is not None


@pytest.mark.asyncio
@respx.mock
async def test_workday_scraper_handles_three_part_board():
    list_payload = {
        "jobPostings": [
            {
                "title": "Staff Engineer",
                "externalPath": "/job/London/Staff-Engineer_R-99",
                "locationsText": "London, UK",
                "postedOn": "Posted Yesterday",
                "bulletFields": ["fallback description text"],
            }
        ]
    }

    respx.post(
        "https://acme.wd1.myworkdayjobs.com/wday/cxs/acme/Careers/jobs"
    ).mock(return_value=httpx.Response(200, json=list_payload))
    # detail endpoint returns 404 — scraper should fall back to bulletFields
    respx.get(
        "https://acme.wd1.myworkdayjobs.com/wday/cxs/acme/Careers"
        "/job/London/Staff-Engineer_R-99"
    ).mock(return_value=httpx.Response(404, json={}))

    async with httpx.AsyncClient() as client:
        scraper = WorkdayScraper(client=client, board="acme/wd1/Careers")
        jobs = [j async for j in scraper.fetch()]

    assert len(jobs) == 1
    j = jobs[0]
    assert j.source == "workday"
    assert j.title == "Staff Engineer"
    assert j.url.startswith("https://acme.wd1.myworkdayjobs.com/en-US/Careers/job/London/")
    assert "fallback description" in j.description
    assert j.posted_at is not None
