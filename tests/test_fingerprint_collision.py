"""Distinct openings that share company/title/location must not collide and
overwrite each other's apply URL — while the SAME job arriving from two
different aggregators must still dedup into one row.
"""

from __future__ import annotations

import pytest

from jobhunt.db import db_session, init_db
from jobhunt.models import Job
from jobhunt.refresh import _persist
from jobhunt.scrapers import RawJob

_TEST_SOURCES = ("test-collision", "test-aggA", "test-aggB")
_TEST_COMPANIES = ("CollisionCo", "CrossSourceCo")


@pytest.fixture(autouse=True)
def _cleanup():
    init_db()
    with db_session() as s:
        s.query(Job).filter(Job.source.in_(_TEST_SOURCES)).delete()
        s.query(Job).filter(Job.company.in_(_TEST_COMPANIES)).delete()
    yield
    with db_session() as s:
        s.query(Job).filter(Job.source.in_(_TEST_SOURCES)).delete()
        s.query(Job).filter(Job.company.in_(_TEST_COMPANIES)).delete()


def test_persist_keeps_distinct_same_source_openings():
    """Two different reqs from the same source (different source_id) with identical
    company/title/location must persist as TWO rows, both apply URLs preserved."""
    with db_session() as s:
        r1 = RawJob(source="test-collision", source_id="req-1",
                    url="https://collisionco.com/jobs/1", company="CollisionCo",
                    title="Software Engineer", location="Cairo, Egypt",
                    description="First distinct opening. " + "detail " * 20)
        r2 = RawJob(source="test-collision", source_id="req-2",
                    url="https://collisionco.com/jobs/2", company="CollisionCo",
                    title="Software Engineer", location="Cairo, Egypt",
                    description="Second distinct opening. " + "detail " * 20)
        assert _persist(s, r1, None) is True
        assert _persist(s, r2, None) is True  # distinct opening → new row, not a merge

    with db_session() as s:
        jobs = s.query(Job).filter(Job.source == "test-collision").all()
        urls = {j.url for j in jobs}
    assert len(jobs) == 2
    assert urls == {"https://collisionco.com/jobs/1", "https://collisionco.com/jobs/2"}


def test_persist_merges_same_job_across_sources():
    """The same job seen on two aggregators (different source, remote-synonym
    location variants) must still collapse into ONE row."""
    with db_session() as s:
        r1 = RawJob(source="test-aggA", source_id="a1",
                    url="https://crosssourceco.com/apply", company="CrossSourceCo",
                    title="Data Analyst", location="Remote",
                    description="Same shared description. " + "body " * 20)
        r2 = RawJob(source="test-aggB", source_id="b1",
                    url="https://crosssourceco.com/apply", company="CrossSourceCo",
                    title="Data Analyst", location="Worldwide",
                    description="Same shared description. " + "body " * 20)
        assert _persist(s, r1, None) is True
        assert _persist(s, r2, None) is False  # cross-source same job → merge

    with db_session() as s:
        jobs = s.query(Job).filter(Job.company == "CrossSourceCo").all()
    assert len(jobs) == 1
