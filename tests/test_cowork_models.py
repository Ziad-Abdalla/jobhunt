"""P6: ApplicantProfile + Application schema basics."""

from __future__ import annotations

import pytest
from sqlalchemy import inspect

from jobhunt.cowork_models import (
    APPLICATION_STATUSES,
    ApplicantProfile,
    Application,
    can_transition,
)
from jobhunt.db import _engine, db_session, init_db
from jobhunt.models import Job

_TEST_COMPANY = "CoworkModelAcme"


@pytest.fixture(autouse=True)
def _cleanup():
    init_db()
    with db_session() as s:
        job_ids = [j.id for j in s.query(Job).filter(Job.company == _TEST_COMPANY)]
        if job_ids:
            s.query(Application).filter(Application.job_id.in_(job_ids)).delete()
        s.query(Job).filter(Job.company == _TEST_COMPANY).delete()
    yield
    with db_session() as s:
        job_ids = [j.id for j in s.query(Job).filter(Job.company == _TEST_COMPANY)]
        if job_ids:
            s.query(Application).filter(Application.job_id.in_(job_ids)).delete()
        s.query(Job).filter(Job.company == _TEST_COMPANY).delete()


def test_tables_exist() -> None:
    insp = inspect(_engine)
    assert insp.has_table("applicant_profile")
    assert insp.has_table("applications")


def test_no_national_id_fields() -> None:
    # Minimal-PII policy (owner decision): the schema must not even have a
    # place to put passport / national-ID data.
    cols = {c["name"] for c in inspect(_engine).get_columns("applicant_profile")}
    for forbidden in ("passport", "national_id", "ssn", "id_number"):
        assert not any(forbidden in c for c in cols), cols


def test_application_unique_per_job() -> None:
    with db_session() as s:
        s.add(Job(
            fingerprint="coworkmdl-" + "1" * 22, source="test-cw", source_id="1",
            url="https://boards.greenhouse.io/x/1", company=_TEST_COMPANY,
            title="Dev", description="d" * 60,
        ))
    with db_session() as s:
        job = s.query(Job).filter(Job.company == _TEST_COMPANY).one()
        s.add(Application(job_id=job.id))
    with db_session() as s:
        job = s.query(Job).filter(Job.company == _TEST_COMPANY).one()
        s.add(Application(job_id=job.id))
        with pytest.raises(Exception):  # noqa: B017 — IntegrityError via commit
            s.commit()
        s.rollback()


def test_state_machine_shape() -> None:
    assert set(APPLICATION_STATUSES) == {
        "queued", "drafted", "approved", "submitting", "submitted",
        "rejected", "failed",
    }
    assert can_transition("queued", "drafted")
    assert can_transition("drafted", "approved")
    assert can_transition("drafted", "rejected")
    assert can_transition("drafted", "drafted")        # re-draft in place
    assert can_transition("approved", "submitting")    # claim (race guard)
    assert can_transition("submitting", "submitted")
    assert can_transition("approved", "rejected")      # human cancel
    assert can_transition("rejected", "queued")        # re-queue
    assert can_transition("failed", "queued")          # re-queue
    assert can_transition("queued", "failed")
    assert not can_transition("queued", "submitted")     # skips all gates
    assert not can_transition("drafted", "submitted")    # skips approve
    assert not can_transition("approved", "submitted")   # skips the claim
    assert not can_transition("submitted", "approved")
    assert not can_transition("submitted", "queued")     # submitted is terminal
    # A claimed (in-flight) application must NOT revert to approved — that
    # would let a second actuator re-claim and double-submit (audit HIGH-1).
    assert not can_transition("submitting", "approved")
    assert can_transition("submitting", "failed")        # the only recovery


def test_profile_defaults_empty() -> None:
    p = ApplicantProfile(id=1)
    assert p.full_name == "" or p.full_name is None


def test_stale_sweep_protects_active_applications() -> None:
    # A stale job with an ACTIVE application must survive the sweep (else the
    # user's queued/approved application is silently orphaned); a stale job
    # with a TERMINAL application is fine to sweep.
    from datetime import timedelta

    from jobhunt.cowork_models import _utcnow as _cw_utcnow
    from jobhunt.refresh import sweep_stale

    from sqlalchemy import text as _text

    old = _cw_utcnow() - timedelta(days=999)
    with db_session() as s:
        # Clear any orphaned applications so a reused SQLite rowid can't
        # collide with the fresh jobs below (unique job_id).
        s.execute(_text("DELETE FROM applications WHERE job_id NOT IN (SELECT id FROM jobs)"))
    with db_session() as s:
        for tag, fp in (("active", "5" * 20), ("terminal", "6" * 20)):
            s.add(Job(
                fingerprint=f"sweepapp-{fp}", source="test-cw", source_id=tag,
                url=f"https://x.com/{tag}", company=_TEST_COMPANY,
                title=f"Sweep {tag}", description="d" * 60, last_seen_at=old,
            ))
    with db_session() as s:
        active_job = s.query(Job).filter(Job.title == "Sweep active").one()
        term_job = s.query(Job).filter(Job.title == "Sweep terminal").one()
        s.add(Application(job_id=active_job.id, status="approved"))
        s.add(Application(job_id=term_job.id, status="rejected"))
        active_id, term_id = active_job.id, term_job.id
    with db_session() as s:
        sweep_stale(s)
    with db_session() as s:
        assert s.get(Job, active_id) is not None  # protected
        assert s.get(Job, term_id) is None         # swept (terminal app)


class TestFullAutoColumns:
    def test_profile_standard_answer_fields(self):
        p = ApplicantProfile(id=99)
        for f in ("cv_path_egypt", "cv_path_remote", "notice_period",
                  "earliest_start", "how_heard_default", "eeo_default"):
            assert hasattr(p, f), f

    def test_application_outcome_fields(self):
        from jobhunt.cowork_models import OUTCOME_VALUES

        a = Application(job_id=1)
        for f in ("queued_by", "annotations", "outcome", "outcome_note",
                  "outcome_updated_at"):
            assert hasattr(a, f), f
        assert OUTCOME_VALUES[0] == ""
        assert "awaiting_reply" in OUTCOME_VALUES
        assert "offer" in OUTCOME_VALUES

    def test_answer_bank_roundtrip(self):
        from jobhunt.cowork_models import AnswerBank

        init_db()
        with db_session() as s:
            s.query(AnswerBank).filter_by(question_norm="notice period").delete()
            s.add(AnswerBank(question="Notice period?",
                             question_norm="notice period", answer="1 month"))
        with db_session() as s:
            row = s.query(AnswerBank).filter_by(question_norm="notice period").one()
            assert row.answer == "1 month"
            s.delete(row)

    def test_forward_migrations_cover_new_columns(self):
        from jobhunt.db import _FORWARD_COLUMNS

        ap = {c for c, _ in _FORWARD_COLUMNS.get("applicant_profile", [])}
        assert {"cv_path_egypt", "cv_path_remote", "notice_period",
                "earliest_start", "how_heard_default", "eeo_default"} <= ap
        apps = {c for c, _ in _FORWARD_COLUMNS.get("applications", [])}
        assert {"queued_by", "annotations", "outcome", "outcome_note",
                "outcome_updated_at"} <= apps
