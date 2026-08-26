import httpx
import pytest
import respx

from jobhunt.scrapers.fourdayweek import FourDayWeekScraper

_API = "https://4dayweek.io/api/jobs"


def _job(**over):
    base = {
        "id": "01a03e10-1f3f-7a5d-b5e8-6027ae83871e",
        "title": "Backend Engineer",
        "slug": "backend-engineer-at-globex-469ea7df",
        "company_name": "Globex",
        "work_arrangement": "remote",
        "locations": [
            {"city": "Telford", "country": "United Kingdom", "is_primary": False},
            {"state": "Ontario", "country": "Canada", "is_primary": True},
        ],
        "posted": 1787747639,
        "schedule_type": "4_day_week_pro_rata",
        "stack": [{"name": "Cloud"}, {"name": "APIs"}],
        "category": "engineering",
        "is_expired": False,
        "company": {"name": "Globex", "slug": "globex"},
        "work_life_score": 92,
    }
    base.update(over)
    return base


@pytest.mark.asyncio
@respx.mock
async def test_parses_payload_and_flattens_locations():
    respx.get(_API).mock(
        return_value=httpx.Response(
            200, json={"jobs": [_job()], "total": 1, "page": 1, "has_more": False}
        )
    )
    async with httpx.AsyncClient() as client:
        jobs = [j async for j in FourDayWeekScraper(client=client, board="").fetch()]

    assert len(jobs) == 1
    j = jobs[0]
    assert j.source == "4dayweek"
    assert j.title == "Backend Engineer"
    assert j.company == "Globex"
    assert j.url == "https://4dayweek.io/job/backend-engineer-at-globex-469ea7df"
    assert j.remote_structured == "remote"
    # Primary location leads, regardless of array order.
    assert j.location == "Ontario, Canada | Telford, United Kingdom"
    assert j.posted_at is not None
    assert j.extra["company_slug"] == "globex"
    assert j.extra["tags"] == ["Cloud", "APIs"]


@pytest.mark.asyncio
@respx.mock
async def test_skips_expired_and_slugless():
    respx.get(_API).mock(
        return_value=httpx.Response(
            200,
            json={
                "jobs": [
                    _job(is_expired=True),
                    _job(slug=""),
                    _job(id="keep-me"),
                ],
                "has_more": False,
            },
        )
    )
    async with httpx.AsyncClient() as client:
        jobs = [j async for j in FourDayWeekScraper(client=client, board="").fetch()]

    assert [j.source_id for j in jobs] == ["keep-me"]


@pytest.mark.asyncio
@respx.mock
async def test_board_filters_by_category():
    respx.get(_API).mock(
        return_value=httpx.Response(
            200,
            json={
                "jobs": [
                    _job(id="eng", category="engineering"),
                    _job(id="prod", category="product"),
                ],
                "has_more": False,
            },
        )
    )
    async with httpx.AsyncClient() as client:
        jobs = [
            j async for j in FourDayWeekScraper(client=client, board="product").fetch()
        ]

    assert [j.source_id for j in jobs] == ["prod"]


@pytest.mark.asyncio
@respx.mock
async def test_follows_pagination_until_has_more_is_false():
    route = respx.get(_API)
    route.side_effect = [
        httpx.Response(200, json={"jobs": [_job(id="p1")], "has_more": True}),
        httpx.Response(200, json={"jobs": [_job(id="p2")], "has_more": False}),
    ]
    async with httpx.AsyncClient() as client:
        jobs = [j async for j in FourDayWeekScraper(client=client, board="").fetch()]

    assert [j.source_id for j in jobs] == ["p1", "p2"]
    assert route.call_count == 2


@pytest.mark.asyncio
@respx.mock
async def test_rate_limit_stops_the_walk_instead_of_raising():
    route = respx.get(_API)
    route.side_effect = [
        httpx.Response(200, json={"jobs": [_job(id="p1")], "has_more": True}),
        httpx.Response(429),
    ]
    async with httpx.AsyncClient() as client:
        jobs = [j async for j in FourDayWeekScraper(client=client, board="").fetch()]

    assert [j.source_id for j in jobs] == ["p1"]
