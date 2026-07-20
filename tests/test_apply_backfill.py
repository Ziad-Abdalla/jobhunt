"""P5: apply_kind/apply_domain schema, NULL-sentinel backfill, _persist wiring."""

from __future__ import annotations

import pytest
from sqlalchemy import inspect, text

from jobhunt.db import _apply_backfill_chunk_once, _engine, db_session, init_db
from jobhunt.models import Job
from jobhunt.refresh import _persist
from jobhunt.scrapers.base import RawJob

_TEST_COMPANY = "ApplyBackfillAcme"


@pytest.fixture(autouse=True)
def _cleanup():
    init_db()
    with db_session() as s:
        s.query(Job).filter(Job.company == _TEST_COMPANY).delete()
    yield
    with db_session() as s:
        s.query(Job).filter(Job.company == _TEST_COMPANY).delete()


def _insert_null_row(fp: str, url: str) -> int:
    """Insert a row with apply_kind NULL (as the forward migration leaves
    pre-P5 rows) via raw SQL so no ORM default interferes."""
    with _engine.begin() as conn:
        conn.execute(
            text(
                "INSERT INTO jobs (fingerprint, source, source_id, url, company, "
                "title, location, remote, level, degree, employment_type, "
                "salary_currency, visa_sponsorship, category, geo_restrict, skills, "
                "languages, description, description_hash, first_seen_at, "
                "last_seen_at, score, salary_estimated, apply_kind, apply_domain) "
                "VALUES (:fp, 'test-apply', '', :url, :company, 'Dev', '', "
                "'unknown', 'unknown', 'unknown', 'unknown', '', 'unknown', "
                "'other', 'unknown', '[]', '[]', '', '', CURRENT_TIMESTAMP, "
                "CURRENT_TIMESTAMP, 0, 0, NULL, '')"
            ),
            {"fp": fp, "url": url, "company": _TEST_COMPANY},
        )
        return conn.execute(
            text("SELECT id FROM jobs WHERE fingerprint = :fp"), {"fp": fp}
        ).scalar_one()


class TestSchema:
    def test_columns_exist(self):
        cols = {c["name"] for c in inspect(_engine).get_columns("jobs")}
        assert "apply_kind" in cols
        assert "apply_domain" in cols

    def test_apply_kind_nullable(self):
        col = next(
            c for c in inspect(_engine).get_columns("jobs") if c["name"] == "apply_kind"
        )
        assert col["nullable"]

    def test_index_exists(self):
        names = {ix["name"] for ix in inspect(_engine).get_indexes("jobs")}
        assert any("apply_kind" in n for n in names)


class TestBackfill:
    def test_null_rows_get_classified(self):
        row_id = _insert_null_row(
            "applybf-" + "1" * 24, "https://boards.greenhouse.io/acme/jobs/1"
        )
        while _apply_backfill_chunk_once() > 0:
            pass
        with _engine.connect() as conn:
            kind, domain = conn.execute(
                text("SELECT apply_kind, apply_domain FROM jobs WHERE id = :id"),
                {"id": row_id},
            ).one()
        assert kind == "ats"
        assert domain == "boards.greenhouse.io"

    def test_unclassifiable_row_marked_unknown_not_revisited(self):
        row_id = _insert_null_row("applybf-" + "2" * 24, "")
        while _apply_backfill_chunk_once() > 0:
            pass
        with _engine.connect() as conn:
            kind = conn.execute(
                text("SELECT apply_kind FROM jobs WHERE id = :id"), {"id": row_id}
            ).scalar_one()
        assert kind == "unknown"  # written explicitly, so never re-picked

    def test_classified_rows_untouched(self):
        row_id = _insert_null_row(
            "applybf-" + "3" * 24, "https://wuzzuf.net/jobs/p/1"
        )
        with _engine.begin() as conn:
            conn.execute(
                text("UPDATE jobs SET apply_kind = 'company_site', "
                     "apply_domain = 'keep.me' WHERE id = :id"),
                {"id": row_id},
            )
        while _apply_backfill_chunk_once() > 0:
            pass
        with _engine.connect() as conn:
            kind, domain = conn.execute(
                text("SELECT apply_kind, apply_domain FROM jobs WHERE id = :id"),
                {"id": row_id},
            ).one()
        assert (kind, domain) == ("company_site", "keep.me")


def _raw(url: str, source_id: str = "sid-1") -> RawJob:
    return RawJob(
        source="test-apply",
        source_id=source_id,
        url=url,
        company=_TEST_COMPANY,
        title="Backend Engineer",
        location="Cairo, Egypt",
        description="d" * 60,
    )


class TestPersistWiring:
    def test_insert_sets_fields(self):
        with db_session() as s:
            assert _persist(s, _raw("https://jobs.lever.co/acme/1"), None)
        with db_session() as s:
            job = s.query(Job).filter(Job.company == _TEST_COMPANY).one()
            assert job.apply_kind == "ats"
            assert job.apply_domain == "jobs.lever.co"

    def test_update_reclassifies_on_url_change(self):
        with db_session() as s:
            assert _persist(s, _raw("https://jobs.lever.co/acme/1"), None)
        with db_session() as s:
            added = _persist(s, _raw("https://stripe.com/jobs/1"), None)
            assert not added  # same fingerprint → update path
        with db_session() as s:
            job = s.query(Job).filter(Job.company == _TEST_COMPANY).one()
            assert job.apply_kind == "company_site"
            assert job.apply_domain == "stripe.com"
