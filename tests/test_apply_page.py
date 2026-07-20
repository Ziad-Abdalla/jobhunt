"""P5: /apply collection page + apply fields on /api/jobs."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from jobhunt.db import db_session, init_db
from jobhunt.main import app
from jobhunt.models import Job

_TEST_COMPANY = "ApplyPageAcme"


@pytest.fixture(autouse=True)
def _seed():
    init_db()
    with db_session() as s:
        s.query(Job).filter(Job.company == _TEST_COMPANY).delete()
        s.add(Job(
            fingerprint="applypage-" + "1" * 22,
            source="test-apply", source_id="a1",
            url="https://boards.greenhouse.io/acme/jobs/1",
            company=_TEST_COMPANY, title="ATS Role Xq", location="Cairo, Egypt",
            description="d" * 60, apply_kind="ats",
            apply_domain="boards.greenhouse.io", score=1.0,
        ))
        s.add(Job(
            fingerprint="applypage-" + "2" * 22,
            source="test-apply", source_id="a2",
            url="https://wuzzuf.net/jobs/p/99",
            company=_TEST_COMPANY, title="Relay Role Xq", location="Cairo, Egypt",
            description="d" * 60, apply_kind="aggregator_relay",
            apply_domain="wuzzuf.net", score=1.0,
        ))
        s.add(Job(
            fingerprint="applypage-" + "3" * 22,
            source="test-apply", source_id="a3",
            url="https://stripe.com/jobs/1",
            company=_TEST_COMPANY, title="OwnSite Role Xq", location="Remote",
            description="d" * 60, apply_kind="company_site",
            apply_domain="stripe.com", score=1.0,
        ))
    yield
    with db_session() as s:
        s.query(Job).filter(Job.company == _TEST_COMPANY).delete()


client = TestClient(app)


class TestApplyPage:
    def test_renders_with_counts(self):
        r = client.get("/apply")
        assert r.status_code == 200
        body = r.text
        assert "ATS form" in body
        assert "Job board" in body
        assert "Company site" in body

    def test_kind_filter_narrows(self):
        r = client.get("/apply", params={"kind": "ats", "q": "Xq"})
        assert "ATS Role Xq" in r.text
        assert "Relay Role Xq" not in r.text
        assert "OwnSite Role Xq" not in r.text

    def test_badges_render_on_apply_page(self):
        r = client.get("/apply", params={"q": "Xq"})
        body = r.text
        assert 'apply-ats' in body
        assert 'apply-aggregator_relay' in body
        assert 'apply-company_site' in body

    def test_badge_not_on_main_jobs_partial(self):
        r = client.get("/jobs", params={"q": "Xq", "company": _TEST_COMPANY})
        assert "ATS Role Xq" in r.text
        assert 'apply-ats' not in r.text

    def test_nav_has_apply(self):
        r = client.get("/apply")
        assert 'href="/apply"' in r.text


class TestApiJobsFields:
    def test_api_jobs_carries_apply_fields(self):
        r = client.get("/api/jobs", params={"company": _TEST_COMPANY, "q": "ATS Role"})
        data = r.json()
        assert data["total"] >= 1
        row = next(x for x in data["results"] if x["title"] == "ATS Role Xq")
        assert row["apply_kind"] == "ats"
        assert row["apply_domain"] == "boards.greenhouse.io"
