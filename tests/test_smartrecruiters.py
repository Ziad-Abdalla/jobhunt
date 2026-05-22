import httpx
import pytest
import respx

from jobhunt.scrapers.smartrecruiters import SmartRecruitersScraper


@pytest.mark.asyncio
@respx.mock
async def test_smartrecruiters_scraper_parses_payload():
    list_payload = {
        "content": [
            {
                "id": "posting-1",
                "name": "Senior Backend Engineer",
                "ref": "https://jobs.smartrecruiters.com/acme/posting-1",
                "releasedDate": "2026-05-18T08:00:00Z",
                "location": {"city": "Berlin", "country": "de"},
                "industry": {"label": "Software"},
                "department": {"label": "Engineering"},
            },
            {
                "id": "posting-2",
                "name": "ML Engineer",
                "releasedDate": "2026-05-15T08:00:00Z",
                "location": {"city": "Remote", "country": "EU"},
                "industry": {"label": "Software"},
            },
        ]
    }
    detail_one = {
        "jobAd": {
            "sections": {
                "jobDescription": {"text": "<p>Own the <b>payments</b> platform.</p>"},
                "qualifications": {"text": "<ul><li>5y backend</li></ul>"},
                "responsibilities": {"text": "<p>Design APIs.</p>"},
            }
        }
    }
    detail_two = {
        "jobAd": {
            "sections": {
                "jobDescription": {"text": "<p>Build <i>ranking</i> models.</p>"},
                "qualifications": {"text": ""},
                "responsibilities": {"text": ""},
            }
        }
    }
    respx.get(
        "https://api.smartrecruiters.com/v1/companies/acme/postings?offset=0&limit=100"
    ).mock(return_value=httpx.Response(200, json=list_payload))
    respx.get(
        "https://api.smartrecruiters.com/v1/companies/acme/postings/posting-1"
    ).mock(return_value=httpx.Response(200, json=detail_one))
    respx.get(
        "https://api.smartrecruiters.com/v1/companies/acme/postings/posting-2"
    ).mock(return_value=httpx.Response(200, json=detail_two))

    async with httpx.AsyncClient() as client:
        scraper = SmartRecruitersScraper(client=client, board="acme")
        jobs = [j async for j in scraper.fetch()]

    assert len(jobs) == 2
    first, second = jobs
    assert first.source == "smartrecruiters"
    assert first.title == "Senior Backend Engineer"
    assert first.url == "https://jobs.smartrecruiters.com/acme/posting-1"
    assert first.posted_at is not None
    assert "payments" in first.description
    assert "<b>" not in first.description  # BeautifulSoup ran
    assert "Berlin" in first.location

    assert second.title == "ML Engineer"
    assert second.url == "https://jobs.smartrecruiters.com/acme/posting-2"
    assert "ranking" in second.description
    assert "<i>" not in second.description
