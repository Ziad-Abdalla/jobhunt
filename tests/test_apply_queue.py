"""P6: queue actions + queue view on /apply."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from jobhunt.cowork_models import Application
from jobhunt.db import db_session, init_db
from jobhunt.main import app
from jobhunt.models import Job

_TEST_COMPANY = "ApplyQueueAcme"
_ORIGIN = {"origin": "http://testserver"}
local = TestClient(app, client=("127.0.0.1", 50000), headers=_ORIGIN)
remote = TestClient(app, client=("203.0.113.9", 50000), headers=_ORIGIN)


def _job_id() -> int:
    with db_session() as s:
        return s.query(Job).filter(Job.company == _TEST_COMPANY).one().id


@pytest.fixture(autouse=True)
def _seed():
    init_db()
    def _clean():
        with db_session() as s:
            ids = [j.id for j in s.query(Job).filter(Job.company == _TEST_COMPANY)]
            if ids:
                s.query(Application).filter(Application.job_id.in_(ids)).delete()
            s.query(Job).filter(Job.company == _TEST_COMPANY).delete()
    _clean()
    with db_session() as s:
        s.add(Job(
            fingerprint="applyq-" + "1" * 25, source="test-q", source_id="q1",
            url="https://boards.greenhouse.io/acme/jobs/9",
            company=_TEST_COMPANY, title="Queue Role Zx", location="Cairo, Egypt",
            description="d" * 60, apply_kind="ats",
            apply_domain="boards.greenhouse.io", score=1.0,
        ))
    yield
    _clean()


class TestQueueAction:
    def test_queue_creates_application(self):
        r = local.post(f"/apply/queue/{_job_id()}", follow_redirects=False)
        assert r.status_code in (302, 303)
        with db_session() as s:
            a = s.query(Application).filter(Application.job_id == _job_id()).one()
            assert a.status == "queued"

    def test_queue_idempotent(self):
        local.post(f"/apply/queue/{_job_id()}")
        local.post(f"/apply/queue/{_job_id()}")
        with db_session() as s:
            n = s.query(Application).filter(Application.job_id == _job_id()).count()
        assert n == 1

    def test_queue_unknown_job_404(self):
        r = local.post("/apply/queue/99999999", follow_redirects=False)
        assert r.status_code == 404


class TestApproveReject:
    def _queued(self) -> int:
        local.post(f"/apply/queue/{_job_id()}")
        with db_session() as s:
            return s.query(Application).filter(Application.job_id == _job_id()).one().id

    def test_approve_requires_drafted(self):
        app_id = self._queued()
        r = local.post(f"/apply/queue/{app_id}/approve", follow_redirects=False)
        assert r.status_code == 409  # queued -> approved skips the draft review

    def test_approve_after_draft(self):
        app_id = self._queued()
        with db_session() as s:
            a = s.get(Application, app_id)
            a.status = "drafted"
            a.fields_filled = {"full_name": "Z"}
        r = local.post(f"/apply/queue/{app_id}/approve", follow_redirects=False)
        assert r.status_code in (302, 303)
        with db_session() as s:
            assert s.get(Application, app_id).status == "approved"

    def test_reject_from_queued(self):
        app_id = self._queued()
        r = local.post(f"/apply/queue/{app_id}/reject", follow_redirects=False)
        assert r.status_code in (302, 303)
        with db_session() as s:
            assert s.get(Application, app_id).status == "rejected"


class TestQueueView:
    def test_queue_view_lists_application(self):
        local.post(f"/apply/queue/{_job_id()}")
        r = local.get("/apply", params={"view": "queue"})
        assert r.status_code == 200
        assert "Queue Role Zx" in r.text
        assert "queued" in r.text

    def test_queue_view_loopback_only(self):
        r = remote.get("/apply", params={"view": "queue"})
        assert r.status_code == 403

    def test_queue_actions_loopback_only(self):
        r = remote.post(f"/apply/queue/{_job_id()}", follow_redirects=False)
        assert r.status_code == 403

    def test_draft_fields_rendered_for_review(self):
        local.post(f"/apply/queue/{_job_id()}")
        with db_session() as s:
            a = s.query(Application).filter(Application.job_id == _job_id()).one()
            a.status = "drafted"
            a.fields_filled = {"full_name": "Draft Name Wq", "email": "d@x.com"}
            a.agent_notes = "left 'referral' blank (unknown field)"
        r = local.get("/apply", params={"view": "queue"})
        assert "Draft Name Wq" in r.text
        assert "left &#39;referral&#39; blank" in r.text or "left 'referral' blank" in r.text
        assert "Approve" in r.text
