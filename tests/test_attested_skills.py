"""AttestedSkill model + profile columns (2026-07-25 CV auto-tailoring)."""
from __future__ import annotations

import json

import pytest
from fastapi.testclient import TestClient

from jobhunt.cowork_models import ApplicantProfile, AttestedSkill
from jobhunt.db import db_session, init_db
from jobhunt.main import app

# base_url gives a loopback Host header (the anti-DNS-rebinding gate); the
# matching Origin satisfies the CSRF middleware on non-/api POSTs. Mirrors
# tests/test_profile.py's TestClient setup.
_ORIGIN = {"origin": "http://127.0.0.1"}


@pytest.fixture
def client():
    return TestClient(
        app, base_url="http://127.0.0.1", client=("127.0.0.1", 50000), headers=_ORIGIN
    )


@pytest.fixture
def remote_client():
    return TestClient(
        app, base_url="http://127.0.0.1", client=("203.0.113.9", 50000), headers=_ORIGIN
    )


@pytest.fixture(autouse=True)
def _clean():
    init_db()
    with db_session() as s:
        s.query(AttestedSkill).delete()
        s.query(ApplicantProfile).delete()
    yield
    with db_session() as s:
        s.query(AttestedSkill).delete()
        s.query(ApplicantProfile).delete()


def test_attested_skill_roundtrip():
    with db_session() as s:
        s.add(AttestedSkill(
            keyword_norm="graphql", display="GraphQL",
            category_target="Backend / Frontend",
            project_targets=["UniVeranstaltungen"],
        ))
    with db_session() as s:
        row = s.query(AttestedSkill).filter_by(keyword_norm="graphql").one()
        assert row.display == "GraphQL"
        assert row.project_targets == ["UniVeranstaltungen"]


def test_profile_tailoring_columns_default_empty():
    with db_session() as s:
        p = s.get(ApplicantProfile, 1) or ApplicantProfile(id=1)
        s.add(p)
    with db_session() as s:
        p = s.get(ApplicantProfile, 1)
        assert p.cv_docx_egypt == "" and p.cv_docx_remote == ""
        assert p.summary_template == "" and p.cv_anchors == ""


def test_attest_upserts_and_normalizes(client):
    r = client.post("/api/tailor/attest", data={
        "keyword": "  GraphQL ", "display": "GraphQL",
        "category_target": "Backend / Frontend",
        "project_targets": ["UniVeranstaltungen"], "job_id": "7"},
        follow_redirects=False)
    assert r.status_code == 303 and r.headers["location"] == "/apply/tailor/7"
    r2 = client.post("/api/tailor/attest", data={
        "keyword": "graphql", "display": "GraphQL v2",
        "category_target": "AI / LLM", "job_id": "7"}, follow_redirects=False)
    assert r2.status_code == 303
    with db_session() as s:
        rows = s.query(AttestedSkill).all()
        assert len(rows) == 1 and rows[0].display == "GraphQL v2"


def test_attest_rejects_em_dash_display(client):
    r = client.post("/api/tailor/attest", data={
        "keyword": "x", "display": "x — y", "job_id": "1"})
    assert r.status_code == 400


def test_attest_requires_loopback(remote_client):
    assert remote_client.post("/api/tailor/attest",
                              data={"keyword": "x"}).status_code == 403


def test_attested_delete(client):
    client.post("/api/tailor/attest", data={
        "keyword": "docker", "display": "Docker",
    }, follow_redirects=False)
    with db_session() as s:
        skill_id = s.query(AttestedSkill).filter_by(keyword_norm="docker").one().id
    r = client.post(f"/profile/attested/{skill_id}/delete", follow_redirects=False)
    assert r.status_code == 303
    with db_session() as s:
        assert s.get(AttestedSkill, skill_id) is None


def test_profile_save_rejects_em_dash_template(client):
    r = client.post("/profile", data={
        "full_name": "Z", "summary_template": "a – b",
    })
    assert r.status_code == 400


def test_calibrate_cv_stores_anchors(client, tmp_path):
    from tests.test_cv_docx import make_cv_docx

    master = tmp_path / "m.docx"
    make_cv_docx(master)
    client.post("/profile", data={
        "full_name": "Z", "cv_docx_remote": str(master),
    }, follow_redirects=False)
    r = client.post("/profile/calibrate-cv", follow_redirects=False)
    assert r.status_code == 303 and "calibrated=1" in r.headers["location"]
    with db_session() as s:
        p = s.get(ApplicantProfile, 1)
        assert "remote" in json.loads(p.cv_anchors)


def test_calibrate_cv_error_when_calibration_fails(client, tmp_path):
    from docx import Document

    bad = tmp_path / "bad.docx"
    Document().save(str(bad))
    client.post("/profile", data={
        "full_name": "Z", "cv_docx_remote": str(bad),
    }, follow_redirects=False)
    r = client.post("/profile/calibrate-cv", follow_redirects=False)
    assert r.status_code == 303 and "calibrate_error=" in r.headers["location"]
    with db_session() as s:
        p = s.get(ApplicantProfile, 1)
        assert p.cv_anchors == ""
