"""P6: ApplicantProfile + Application schema basics."""

from __future__ import annotations

import pytest
from sqlalchemy import inspect

from jobhunt.cowork_models import (
    APPLICATION_STATUSES,
    Application,
    ApplicantProfile,
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
        "queued", "drafted", "approved", "submitted", "rejected", "failed",
    }
    assert can_transition("queued", "drafted")
    assert can_transition("drafted", "approved")
    assert can_transition("drafted", "rejected")
    assert can_transition("approved", "submitted")
    assert can_transition("queued", "failed")
    assert not can_transition("queued", "submitted")   # skips both human gates
    assert not can_transition("drafted", "submitted")  # skips approve gate
    assert not can_transition("submitted", "approved")
    assert not can_transition("rejected", "approved")


def test_profile_defaults_empty() -> None:
    p = ApplicantProfile(id=1)
    assert p.full_name == "" or p.full_name is None
