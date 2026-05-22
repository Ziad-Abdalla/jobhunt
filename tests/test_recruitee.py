import httpx
import pytest
import respx

from jobhunt.scrapers.recruitee import RecruiteeScraper


@pytest.mark.asyncio
@respx.mock
async def test_recruitee_scraper_parses_payload():
    payload = {
        "offers": [
            {
                "id": 5511,
                "title": "Full-Stack Developer",
                "slug": "full-stack-developer",
                "city": "Amsterdam",
                "country": "Netherlands",
                "description": "<p>Ship features with <b>TypeScript</b>.</p>",
                "requirements": "<ul><li>3+ years</li></ul>",
                "created_at": "2026-05-20T10:15:00Z",
                "careers_url": "https://acme.recruitee.com/o/full-stack-developer",
                "employment_type_code": "permanent",
                "min_hours": 32,
                "max_hours": 40,
            },
            {
                "id": 5512,
                "title": "DevOps Engineer",
                "slug": "devops-engineer",
                "city": "Remote",
                "country": "EU",
                "description": "<p>Operate <em>Kubernetes</em> clusters.</p>",
                "requirements": "",
                "created_at": "2026-05-17T11:00:00Z",
                "employment_type_code": "permanent",
            },
        ]
    }
    respx.get("https://acme.recruitee.com/api/offers/").mock(
        return_value=httpx.Response(200, json=payload)
    )

    async with httpx.AsyncClient() as client:
        scraper = RecruiteeScraper(client=client, board="acme")
        jobs = [j async for j in scraper.fetch()]

    assert len(jobs) == 2
    first, second = jobs
    assert first.source == "recruitee"
    assert first.title == "Full-Stack Developer"
    assert first.url == "https://acme.recruitee.com/o/full-stack-developer"
    assert first.posted_at is not None
    assert "TypeScript" in first.description
    assert "<b>" not in first.description  # BeautifulSoup ran
    assert "3+ years" in first.description
    assert "Amsterdam" in first.location

    assert second.title == "DevOps Engineer"
    assert second.url == "https://acme.recruitee.com/o/devops-engineer"
    assert "Kubernetes" in second.description
    assert "<em>" not in second.description
