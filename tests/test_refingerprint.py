"""One-time fingerprint migration after the Unicode normalization change (P3).

dedup normalization became Unicode-aware + NFC; stored fingerprints for rows
containing non-ASCII text no longer match what _persist computes. The migration
rewrites them once (plain AND P1-salted schemes), merging on collision.
"""

from __future__ import annotations

import pytest

from jobhunt.db import _legacy_fingerprint, _refingerprint_once, db_session, init_db
from jobhunt.dedup import fingerprint
from jobhunt.models import Job

_TEST_COMPANIES = ("RefpAcme Egypt", "RefpAcme")


@pytest.fixture(autouse=True)
def _cleanup():
    init_db()
    with db_session() as s:
        s.query(Job).filter(Job.company.in_(_TEST_COMPANIES)).delete()
    yield
    with db_session() as s:
        s.query(Job).filter(Job.company.in_(_TEST_COMPANIES)).delete()


def _mk_job(company, title, location, fp, source="test-refp", source_id=""):
    with db_session() as s:
        s.add(Job(
            fingerprint=fp, source=source, source_id=source_id,
            url=f"https://x.com/{fp[:8]}", company=company, title=title,
            location=location, description="d" * 60,
        ))


class TestLegacyFingerprint:
    def test_ascii_matches_current(self):
        # For pure-ASCII inputs old and new normalization agree.
        assert _legacy_fingerprint("RefpAcme", "Backend Engineer", "London") == \
            fingerprint("RefpAcme", "Backend Engineer", "London")

    def test_arabic_differs_from_current(self):
        assert _legacy_fingerprint("RefpAcme", "محاسب", "Cairo") != \
            fingerprint("RefpAcme", "محاسب", "Cairo")


class TestRefingerprint:
    def test_plain_row_updated(self):
        old_fp = _legacy_fingerprint("RefpAcme Egypt", "محاسب", "Cairo, Egypt")
        _mk_job("RefpAcme Egypt", "محاسب", "Cairo, Egypt", old_fp)
        changed = _refingerprint_once()
        assert changed >= 1
        with db_session() as s:
            job = s.query(Job).filter(Job.company == "RefpAcme Egypt").one()
            assert job.fingerprint == fingerprint("RefpAcme Egypt", "محاسب", "Cairo, Egypt")

    def test_salted_row_updated_with_salt(self):
        old_fp = _legacy_fingerprint("RefpAcme Egypt", "محاسب", "Cairo, Egypt", salt="wz-2")
        _mk_job("RefpAcme Egypt", "محاسب", "Cairo, Egypt", old_fp, source_id="wz-2")
        _refingerprint_once()
        with db_session() as s:
            job = s.query(Job).filter(Job.company == "RefpAcme Egypt").one()
            assert job.fingerprint == fingerprint(
                "RefpAcme Egypt", "محاسب", "Cairo, Egypt", salt="wz-2"
            )

    def test_ascii_row_untouched(self):
        fp = fingerprint("RefpAcme", "Backend Engineer", "London")
        _mk_job("RefpAcme", "Backend Engineer", "London", fp)
        _refingerprint_once()
        with db_session() as s:
            job = s.query(Job).filter(Job.company == "RefpAcme").one()
            assert job.fingerprint == fp

    def test_collision_keeps_one_row(self):
        # A migrating old-scheme row whose NEW fingerprint is already owned by
        # another row: the migration must keep exactly one, not crash.
        old_a = _legacy_fingerprint("RefpAcme Egypt", "محاسب", "Cairo, Egypt")
        _mk_job("RefpAcme Egypt", "محاسب", "Cairo, Egypt", old_a)
        new_fp = fingerprint("RefpAcme Egypt", "محاسب", "Cairo, Egypt")
        _mk_job("RefpAcme Egypt", "محاسب", "Cairo, Egypt", new_fp, source_id="dup")
        _refingerprint_once()
        with db_session() as s:
            rows = s.query(Job).filter(Job.fingerprint == new_fp).all()
            assert len(rows) == 1
