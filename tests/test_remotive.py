import httpx
import pytest
import respx

from jobhunt.scrapers.remotive import RemotiveScraper

_PAYLOAD = {
    "job-count": 1,
    "jobs": [
        {
            "id": 2091069,
            "url": "https://remotive.com/remote-jobs/software-dev/backend-engineer-2091069",
            "title": "Backend Engineer",
            "company_name": "Globex",
            "company_logo": "https://remotive.com/job/2091069/logo",
            "category": "Software Development",
            "tags": ["python", "postgres"],
            "job_type": "full_time",
            "publication_date": "2026-07-16T13:28:02",
            "candidate_required_location": "Worldwide",
            "salary": "$90k - $120k",
            "description": "<p>We use <b>Python</b> and Postgres.</p>",
        }
    ],
}


@pytest.mark.asyncio
@respx.mock
async def test_remotive_parses_payload():
    respx.get("https://remotive.com/api/remote-jobs").mock(
        return_value=httpx.Response(200, json=_PAYLOAD)
    )
    async with httpx.AsyncClient() as client:
        jobs = [j async for j in RemotiveScraper(client=client, board="").fetch()]

    assert len(jobs) == 1
    j = jobs[0]
    assert j.source == "remotive"
    assert j.title == "Backend Engineer"
    assert j.company == "Globex"
    assert j.url.endswith("backend-engineer-2091069")
    assert j.source_id == "2091069"
    assert j.remote_structured == "remote"  # Remotive is remote-only
    assert j.location == "Worldwide"
    assert "Python" in j.description  # HTML stripped to text
    # "full_time" must normalize into the pipeline's map (which lacks the underscore form)
    assert j.employment_type in ("full-time", "Full-time")
