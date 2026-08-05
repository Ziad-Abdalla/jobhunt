"""Server-side auto-approve (owner override 2026-08-05, JOBHUNT_AUTO_APPROVE).

Reverses the universal-approve-tap posture ON THE OWNER'S EXPLICIT
INSTRUCTION: a non-error draft is approved on arrival and the actuator's
derived answers to unmapped questions join the answer bank. Default stays
OFF — shipped behavior is unchanged without the env toggle.
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from jobhunt.cowork_models import AnswerBank, Application
from jobhunt.db import db_session, init_db
from jobhunt.main import app
from jobhunt.models import Job

_TEST_COMPANY = "AutoApproveAcme"
_ORIGIN = {"origin": "http://127.0.0.1"}
local = TestClient(app, base_url="http://127.0.0.1",
                   client=("127.0.0.1", 50000), headers=_ORIGIN)


@pytest.fixture(autouse=True)
def _seed(monkeypatch):
    from jobhunt.config import settings

    monkeypatch.setattr(settings, "cowork_export", True)
    init_db()

    def _clean():
        with db_session() as s:
            ids = [j.id for j in s.query(Job).filter(Job.company == _TEST_COMPANY)]
            if ids:
                s.query(Application).filter(Application.job_id.in_(ids)).delete()
            s.query(Job).filter(Job.company == _TEST_COMPANY).delete()
            s.query(AnswerBank).delete()

    _clean()
    with db_session() as s:
        for n in (1, 2):
            s.add(Job(
                fingerprint=f"autoappr-{n}" + "1" * 20, source="test-aa",
                source_id=f"aa{n}", url=f"https://boards.greenhouse.io/acme/jobs/{n}",
                company=_TEST_COMPANY, title=f"Auto Role {n}",
                location="Cairo, Egypt", description="d" * 60, apply_kind="ats",
                apply_domain="boards.greenhouse.io", score=1.0,
            ))
    yield
    _clean()


@pytest.fixture()
def _auto_on(monkeypatch):
    from jobhunt.config import settings

    monkeypatch.setattr(settings, "auto_approve", True)


@pytest.fixture(autouse=True)
def _pings(monkeypatch):
    sink: list = []
    from jobhunt import main as main_mod

    monkeypatch.setattr(main_mod, "send_all", lambda *a, **k: sink.append(a) or {})
    return sink


def _queued_ids() -> list[int]:
    out = []
    with db_session() as s:
        job_ids = [j.id for j in s.query(Job).filter(Job.company == _TEST_COMPANY)
                   .order_by(Job.id)]
    for jid in job_ids:
        local.post(f"/apply/queue/{jid}")
        with db_session() as s:
            out.append(s.query(Application)
                       .filter(Application.job_id == jid).one().id)
    return out


def test_default_off_draft_stays_drafted(_pings):
    app_id = _queued_ids()[0]
    r = local.post("/api/cowork/draft", json={
        "application_id": app_id, "fields_filled": {"full_name": "Z"},
    })
    assert r.json()["status"] == "drafted"
    with db_session() as s:
        assert s.get(Application, app_id).status == "drafted"
    assert "raft ready" in _pings[0][0]


def test_auto_approve_moves_to_approved(_auto_on, _pings):
    app_id = _queued_ids()[0]
    r = local.post("/api/cowork/draft", json={
        "application_id": app_id, "fields_filled": {"full_name": "Z"},
    })
    assert r.json()["status"] == "approved"
    with db_session() as s:
        a = s.get(Application, app_id)
        assert a.status == "approved"
        assert a.annotations["auto_approved"] is True
        assert a.annotations["auto_approved_on"]
    assert "auto-approved" in _pings[0][0]


def test_auto_approve_banks_unmapped_answers(_auto_on):
    app_id = _queued_ids()[0]
    local.post("/api/cowork/draft", json={
        "application_id": app_id,
        "fields_filled": {
            "full_name": "Z",
            "cv": "Z_CV_Acme.docx (tailored)",
            "Do you have a notice period?": "No, available immediately",
        },
    })
    with db_session() as s:
        rows = {b.question_norm: b.answer for b in s.query(AnswerBank).all()}
    assert rows.get("do you have a notice period") == "No, available immediately"
    # mapped keys and the cv entry must NOT enter the bank
    assert "full name" not in rows
    assert "cv" not in rows


def test_auto_approve_error_draft_stays_failed(_auto_on):
    app_id = _queued_ids()[0]
    r = local.post("/api/cowork/draft", json={
        "application_id": app_id, "error": "listing gone",
    })
    assert r.json()["status"] == "failed"
    with db_session() as s:
        assert s.get(Application, app_id).status == "failed"


def test_auto_approve_parks_draft_with_blank_question(_auto_on):
    # Owner rule pair: approve everything, but never submit a blank answer.
    # A blank unmapped question means nothing in the owner's data could
    # answer it — that draft waits for the human once.
    app_id = _queued_ids()[0]
    r = local.post("/api/cowork/draft", json={
        "application_id": app_id,
        "fields_filled": {"full_name": "Z", "Desired salary in USD?": ""},
    })
    assert r.json()["status"] == "drafted"
    with db_session() as s:
        assert s.get(Application, app_id).status == "drafted"


def test_auto_approve_daily_cap_parks_draft(_auto_on, monkeypatch):
    from jobhunt.config import settings

    monkeypatch.setattr(settings, "auto_approve_daily_cap", 1)
    first, second = _queued_ids()
    r1 = local.post("/api/cowork/draft", json={
        "application_id": first, "fields_filled": {"full_name": "Z"},
    })
    assert r1.json()["status"] == "approved"
    r2 = local.post("/api/cowork/draft", json={
        "application_id": second, "fields_filled": {"full_name": "Z"},
    })
    assert r2.json()["status"] == "drafted"
    with db_session() as s:
        assert s.get(Application, second).status == "drafted"
