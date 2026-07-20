"""Geo-eligibility extraction (P3) — 'Remote (US only)' must not look
apply-able from Egypt."""

from __future__ import annotations

import pytest

from jobhunt.extract import extract_geo


@pytest.mark.parametrize("text,expected", [
    # us-only
    ("This role is US only.", "us-only"),
    ("Open to candidates located in the United States only", "us-only"),
    ("You must be authorized to work in the United States", "us-only"),
    ("Must have US work authorization", "us-only"),
    ("Applicants must be based in the US.", "us-only"),
    # uk-only
    ("You must have the right to work in the UK", "uk-only"),
    ("UK only — no visa sponsorship", "uk-only"),
    # eu-only
    ("Candidates must be based in the EU", "eu-only"),
    ("EU/EEA work permit required", "eu-only"),
    ("This position is open to Europe only", "eu-only"),
    # restricted-other
    ("Must be located in Canada", "restricted-other"),
    ("Requires 4 hours timezone overlap with PST", "restricted-other"),
    ("Working hours within CET +/- 2 hours", "restricted-other"),
    # unrestricted
    ("Work from anywhere in the world", "unrestricted"),
    ("Fully remote, no location restrictions", "unrestricted"),
    ("We hire globally distributed teammates", "unrestricted"),
    ("Open to candidates worldwide", "unrestricted"),
    # unknown
    ("We are a fast-growing startup looking for a backend engineer.", "unknown"),
    ("", "unknown"),
])
def test_buckets(text, expected):
    assert extract_geo(text) == expected


def test_specific_region_beats_unrestricted():
    text = "Work from anywhere in the world — as long as you are US based candidates only."
    assert extract_geo(text) == "us-only"


def test_title_is_searched_too():
    assert extract_geo("", title="Backend Engineer (Remote, US only)") == "us-only"


# ---------------------------------------------------------------------------
# Persistence + filter + UI round-trip
# ---------------------------------------------------------------------------

from fastapi.testclient import TestClient  # noqa: E402

from jobhunt.db import db_session, init_db  # noqa: E402
from jobhunt.filters import JobQuery, search  # noqa: E402
from jobhunt.main import app  # noqa: E402
from jobhunt.models import Job  # noqa: E402
from jobhunt.refresh import _persist  # noqa: E402
from jobhunt.scrapers.base import RawJob  # noqa: E402

_TEST_SOURCE = "test-geo"


@pytest.fixture()
def clean_db():
    init_db()
    with db_session() as s:
        s.query(Job).filter(Job.source == _TEST_SOURCE).delete()
    yield
    with db_session() as s:
        s.query(Job).filter(Job.source == _TEST_SOURCE).delete()


class TestGeoPersistAndFilter:
    def test_persist_sets_geo_restrict(self, clean_db):
        raw = RawJob(
            source=_TEST_SOURCE, source_id="r1", url="https://x.com/1",
            company="Remote Co", title="Backend Engineer",
            location="Remote",
            description="Fully remote role. You must be authorized to work in the United States. " * 2,
        )
        with db_session() as s:
            _persist(s, raw, company_override=None)
        with db_session() as s:
            job = s.query(Job).filter(Job.source == _TEST_SOURCE).one()
            assert job.geo_restrict == "us-only"

    def test_filter_by_geo(self, clean_db):
        descriptions = [
            "Work from anywhere in the world. Totally flexible location.",
            "You must be authorized to work in the United States. US only.",
        ]
        with db_session() as s:
            for i, desc in enumerate(descriptions):
                _persist(s, RawJob(
                    source=_TEST_SOURCE, source_id=f"g{i}", url=f"https://x.com/g{i}",
                    company=f"GeoCo {i}", title=f"Engineer {i}", location="Remote",
                    description=desc * 2,
                ), company_override=None)
        with db_session() as s:
            rows = search(s, JobQuery(geo="unrestricted", company="GeoCo"))
            assert len(rows) == 1
            assert rows[0].geo_restrict == "unrestricted"


def test_api_jobs_exposes_geo():
    init_db()
    client = TestClient(app)
    resp = client.get("/api/jobs")
    assert resp.status_code == 200
    body = resp.json()
    if body["results"]:
        assert "geo_restrict" in body["results"][0]


def test_index_renders_geo_dropdown():
    init_db()
    client = TestClient(app)
    resp = client.get("/")
    assert resp.status_code == 200
    assert 'name="geo"' in resp.text
    assert "Worldwide-friendly" in resp.text
