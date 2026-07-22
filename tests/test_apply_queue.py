"""P6: queue actions + queue view on /apply."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from jobhunt.cowork_models import Application
from jobhunt.db import db_session, init_db
from jobhunt.main import app
from jobhunt.models import Job

_TEST_COMPANY = "ApplyQueueAcme"
_ORIGIN = {"origin": "http://127.0.0.1"}
local = TestClient(app, base_url="http://127.0.0.1", client=("127.0.0.1", 50000), headers=_ORIGIN)
remote = TestClient(app, base_url="http://127.0.0.1", client=("203.0.113.9", 50000), headers=_ORIGIN)


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

    def test_cancel_after_approve(self):
        app_id = self._queued()
        with db_session() as s:
            a = s.get(Application, app_id)
            a.status = "approved"
        r = local.post(f"/apply/queue/{app_id}/reject", follow_redirects=False)
        assert r.status_code in (302, 303)
        with db_session() as s:
            assert s.get(Application, app_id).status == "rejected"


class TestRequeue:
    def test_requeue_after_rejected(self):
        # A rejected/failed application is NOT a dead end — the Queue button
        # re-activates it (important for board-account Wuzzuf jobs).
        local.post(f"/apply/queue/{_job_id()}")
        with db_session() as s:
            a = s.query(Application).filter(Application.job_id == _job_id()).one()
            a.status = "failed"
            a.error = "board account required"
            app_id = a.id
        local.post(f"/apply/queue/{_job_id()}")
        with db_session() as s:
            a = s.get(Application, app_id)
            assert a.status == "queued"
            assert a.error == ""
        # Still one row — re-queue reuses it, never duplicates.
        with db_session() as s:
            assert s.query(Application).filter(
                Application.job_id == _job_id()
            ).count() == 1

    def test_requeue_clears_stale_artifacts(self):
        # Audit LOW-1: re-queuing a terminal row must clear the old receipt/
        # draft so it doesn't misread as a completed submission.
        local.post(f"/apply/queue/{_job_id()}")
        with db_session() as s:
            a = s.query(Application).filter(Application.job_id == _job_id()).one()
            a.status = "submitted"
            a.receipt = "old-msg-id"
            a.fields_filled = {"full_name": "Z"}
            a.agent_notes = "old notes"
            app_id = a.id
        # submitted isn't re-queueable; force to failed to exercise re-queue.
        with db_session() as s:
            s.get(Application, app_id).status = "failed"
        local.post(f"/apply/queue/{_job_id()}")
        with db_session() as s:
            a = s.get(Application, app_id)
            assert a.status == "queued"
            assert a.receipt == ""
            assert a.fields_filled == {}
            assert a.agent_notes == ""


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


def _queued_id() -> int:
    local.post(f"/apply/queue/{_job_id()}")
    with db_session() as s:
        return s.query(Application).filter(Application.job_id == _job_id()).one().id


def _walk_to(app_id: int, status: str) -> None:
    with db_session() as s:
        s.get(Application, app_id).status = status


class TestDraftAnnotations:
    @pytest.fixture(autouse=True)
    def _cowork_on(self, monkeypatch):
        from jobhunt.config import settings

        monkeypatch.setattr(settings, "cowork_export", True)

    def test_clean_draft_annotates_clean(self, monkeypatch):
        pings = []
        from jobhunt import main as main_mod

        monkeypatch.setattr(main_mod, "send_all", lambda *a, **k: pings.append(a) or {})
        app_id = _queued_id()
        r = local.post("/api/cowork/draft", json={
            "application_id": app_id, "fields_filled": {"full_name": "Z"},
        })
        assert r.status_code == 200
        with db_session() as s:
            ann = s.get(Application, app_id).annotations or {}
        assert ann["clean_mapping"] is True
        assert ann["sensitive_fields"] == []
        assert pings and "raft ready" in pings[0][0]
        assert "clean" in pings[0][1]

    def test_flagged_draft_annotates_and_pings_flags(self, monkeypatch):
        pings = []
        from jobhunt import main as main_mod

        monkeypatch.setattr(main_mod, "send_all", lambda *a, **k: pings.append(a) or {})
        app_id = _queued_id()
        local.post("/api/cowork/draft", json={
            "application_id": app_id,
            "fields_filled": {"desired_salary": "50k", "weird_field": "stuff",
                              "notice period?": ""},
            "agent_notes": "JD contained instruction-like text",
        })
        with db_session() as s:
            ann = s.get(Application, app_id).annotations or {}
        assert ann["clean_mapping"] is False
        assert "desired_salary" in ann["sensitive_fields"]
        assert ann["agent_flags"] is True
        assert ann["unanswered"] == ["notice period?"]
        assert "flagged" in pings[0][1]

    def test_failed_draft_no_annotations_no_ping(self, monkeypatch):
        pings = []
        from jobhunt import main as main_mod

        monkeypatch.setattr(main_mod, "send_all", lambda *a, **k: pings.append(a) or {})
        app_id = _queued_id()
        local.post("/api/cowork/draft", json={
            "application_id": app_id, "error": "board account required",
        })
        with db_session() as s:
            a = s.get(Application, app_id)
        assert a.status == "failed"
        assert not pings


class TestReceiptStartsOutcome:
    @pytest.fixture(autouse=True)
    def _cowork_on(self, monkeypatch):
        from jobhunt.config import settings

        monkeypatch.setattr(settings, "cowork_export", True)

    def test_submitted_sets_awaiting_reply_and_pings(self, monkeypatch):
        pings = []
        from jobhunt import main as main_mod

        monkeypatch.setattr(main_mod, "send_all", lambda *a, **k: pings.append(a) or {})
        app_id = _queued_id()
        _walk_to(app_id, "submitting")
        r = local.post("/api/cowork/receipt", json={
            "application_id": app_id, "receipt": "msg-id-1",
        })
        assert r.status_code == 200
        with db_session() as s:
            a = s.get(Application, app_id)
        assert a.outcome == "awaiting_reply"
        assert a.outcome_updated_at is not None
        assert pings and "ubmitted" in pings[0][0]

    def test_failed_receipt_no_outcome(self, monkeypatch):
        from jobhunt import main as main_mod

        monkeypatch.setattr(main_mod, "send_all", lambda *a, **k: {})
        app_id = _queued_id()
        _walk_to(app_id, "submitting")
        local.post("/api/cowork/receipt", json={
            "application_id": app_id, "error": "off-allowlist redirect",
        })
        with db_session() as s:
            assert s.get(Application, app_id).outcome == ""


def _drafted_id(annotations: dict | None = None) -> int:
    app_id = _queued_id()
    with db_session() as s:
        a = s.get(Application, app_id)
        a.status = "drafted"
        a.fields_filled = {"full_name": "Z"}
        if annotations is not None:
            a.annotations = annotations
    return app_id


class TestApproveWithAnswers:
    @pytest.fixture(autouse=True)
    def _clean_bank(self):
        from jobhunt.cowork_models import AnswerBank

        def wipe():
            with db_session() as s:
                s.query(AnswerBank).delete()
        wipe()
        yield
        wipe()

    def test_approve_saves_bank_answers(self):
        from jobhunt.cowork_models import AnswerBank

        app_id = _drafted_id()
        r = local.post(f"/apply/queue/{app_id}/approve",
                       data={"bank__Notice period?": "1 month",
                             "bank__empty one": ""},
                       follow_redirects=False)
        assert r.status_code == 303
        with db_session() as s:
            assert s.get(Application, app_id).status == "approved"
            rows = {b.question_norm: b.answer for b in s.query(AnswerBank)}
        assert rows.get("notice period") == "1 month"
        assert "empty one" not in rows  # blanks are not saved

    def test_approve_upserts_existing_question(self):
        from jobhunt.cowork_models import AnswerBank

        with db_session() as s:
            s.add(AnswerBank(question="Notice period?",
                             question_norm="notice period", answer="old"))
        app_id = _drafted_id()
        local.post(f"/apply/queue/{app_id}/approve",
                   data={"bank__Notice period?": "new"}, follow_redirects=False)
        with db_session() as s:
            rows = s.query(AnswerBank).filter_by(question_norm="notice period").all()
        assert len(rows) == 1 and rows[0].answer == "new"

    def test_approve_rejects_secret_answers(self):
        app_id = _drafted_id()
        r = local.post(f"/apply/queue/{app_id}/approve",
                       data={"bank__q": "ghp_" + "a" * 36}, follow_redirects=False)
        assert r.status_code == 400
        with db_session() as s:
            assert s.get(Application, app_id).status == "drafted"  # not approved

    def test_plain_approve_still_works(self):
        app_id = _drafted_id()
        r = local.post(f"/apply/queue/{app_id}/approve", follow_redirects=False)
        assert r.status_code == 303


class TestQueueUiAnnotations:
    def test_chips_answers_and_auto_badge_render(self):
        app_id = _drafted_id({
            "clean_mapping": False, "unmapped_fields": ["x"],
            "agent_flags": True, "sensitive_fields": ["desired_salary"],
            "unanswered": ["notice period?"],
        })
        with db_session() as s:
            s.get(Application, app_id).queued_by = "auto"
        r = local.get("/apply?view=queue")
        assert "auto-queued" in r.text
        assert "desired_salary" in r.text
        assert 'name="bank__notice period?"' in r.text


class TestBulkRejectAuto:
    def test_rejects_only_queued_auto(self):
        drafted = _drafted_id()
        with db_session() as s:
            s.get(Application, drafted).queued_by = "auto"
        # a second job so we can have a queued auto row alongside
        with db_session() as s:
            s.add(Job(
                fingerprint="applyq-" + "2" * 25, source="test-q", source_id="q2",
                url="https://boards.greenhouse.io/acme/jobs/10",
                company=_TEST_COMPANY, title="Queue Role Two", location="Cairo, Egypt",
                description="d" * 60, apply_kind="ats",
                apply_domain="boards.greenhouse.io", score=1.0,
            ))
        with db_session() as s:
            j2 = s.query(Job).filter(Job.source_id == "q2",
                                     Job.company == _TEST_COMPANY).one()
            s.add(Application(job_id=j2.id, queued_by="auto"))
        r = local.post("/apply/queue/reject-auto", follow_redirects=False)
        assert r.status_code == 303
        with db_session() as s:
            assert s.get(Application, drafted).status == "drafted"  # untouched
            j2 = s.query(Job).filter(Job.source_id == "q2",
                                     Job.company == _TEST_COMPANY).one()
            a2 = s.query(Application).filter(Application.job_id == j2.id).one()
            assert a2.status == "rejected"

    def test_loopback_gated(self):
        assert remote.post("/apply/queue/reject-auto").status_code == 403


class TestOutcomeEndpoints:
    @pytest.fixture(autouse=True)
    def _cowork_on(self, monkeypatch):
        from jobhunt.config import settings

        monkeypatch.setattr(settings, "cowork_export", True)

    def _submitted_id(self) -> int:
        app_id = _queued_id()
        _walk_to(app_id, "submitted")
        return app_id

    def test_cowork_outcome_on_submitted(self, monkeypatch):
        pings = []
        from jobhunt import main as main_mod

        monkeypatch.setattr(main_mod, "send_all", lambda *a, **k: pings.append(a) or {})
        app_id = self._submitted_id()
        r = local.post("/api/cowork/outcome", json={
            "application_id": app_id, "outcome": "interview",
            "note": "phone screen Tuesday",
        })
        assert r.status_code == 200
        with db_session() as s:
            a = s.get(Application, app_id)
        assert a.outcome == "interview"
        assert a.outcome_note == "phone screen Tuesday"
        assert pings

    def test_outcome_rejected_on_non_submitted(self):
        app_id = _queued_id()
        r = local.post("/api/cowork/outcome", json={
            "application_id": app_id, "outcome": "interview",
        })
        assert r.status_code == 409

    def test_outcome_value_allow_listed(self):
        app_id = self._submitted_id()
        r = local.post("/api/cowork/outcome", json={
            "application_id": app_id, "outcome": "ghosted-forever",
        })
        assert r.status_code == 400
        r2 = local.post("/api/cowork/outcome", json={
            "application_id": app_id, "outcome": "",
        })
        assert r2.status_code == 400  # '' is internal-only, not settable

    def test_outcome_gated(self):
        app_id = self._submitted_id()
        assert remote.post("/api/cowork/outcome", json={
            "application_id": app_id, "outcome": "replied",
        }).status_code == 403

    def test_human_outcome_form(self, monkeypatch):
        from jobhunt import main as main_mod

        monkeypatch.setattr(main_mod, "send_all", lambda *a, **k: {})
        app_id = self._submitted_id()
        r = local.post(f"/apply/queue/{app_id}/outcome",
                       data={"outcome": "offer", "note": ""},
                       follow_redirects=False)
        assert r.status_code == 303
        with db_session() as s:
            assert s.get(Application, app_id).outcome == "offer"
