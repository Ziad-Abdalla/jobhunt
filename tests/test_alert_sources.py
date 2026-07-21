"""P7: per-saved-search source filter + priority flag."""

from __future__ import annotations

import asyncio

import pytest

from jobhunt import alerts as alerts_mod
from jobhunt.db import db_session, init_db
from jobhunt.models import Job, SavedSearch


@pytest.fixture(autouse=True)
def _clean():
    init_db()
    with db_session() as s:
        s.query(SavedSearch).filter(SavedSearch.name.like("AlertSrc%")).delete()
        s.query(Job).filter(Job.company == "AlertSrcAcme").delete()
        # check_alerts() iterates EVERY saved search — including the user's
        # real ones in the live DB — and stamps notified_job_ids /
        # last_notified_at on them, silently eating their next real alert.
        # Snapshot that state and restore it after the test.
        alert_state = {
            ss.id: (list(ss.notified_job_ids or []), ss.last_notified_at)
            for ss in s.query(SavedSearch).all()
        }
    yield
    with db_session() as s:
        s.query(SavedSearch).filter(SavedSearch.name.like("AlertSrc%")).delete()
        s.query(Job).filter(Job.company == "AlertSrcAcme").delete()
        for ss in s.query(SavedSearch).all():
            if ss.id in alert_state:
                ss.notified_job_ids, ss.last_notified_at = alert_state[ss.id]


def _seed_jobs():
    with db_session() as s:
        for i, src in enumerate(("wuzzuf", "greenhouse")):
            s.add(Job(
                fingerprint=f"alertsrc-{src}-{'1'*18}", source=src, source_id=str(i),
                url=f"https://x.com/{src}", company="AlertSrcAcme",
                title="AlertSrc Engineer", location="Cairo", description="d" * 60,
                score=1.0,
            ))


def test_source_filter_narrows_notifications(monkeypatch):
    sent = []
    monkeypatch.setattr(alerts_mod, "send_all", lambda *a, **k: sent.append(a) or {})
    _seed_jobs()
    with db_session() as s:
        s.add(SavedSearch(
            name="AlertSrc wuzzuf-only",
            query_json={"q": "AlertSrc Engineer", "sources": ["wuzzuf"]},
            notify=True, notified_job_ids=[],
        ))
    asyncio.run(alerts_mod.check_alerts())
    # Only the wuzzuf job should have produced an alert. Count only sends
    # about OUR seeded jobs — the live DB may hold the user's real saved
    # searches, whose first-time notifications would inflate a raw count.
    mine = [a for a in sent if "AlertSrcAcme" in a[1]]
    assert len(mine) == 1
    assert "AlertSrc Engineer @ AlertSrcAcme" in mine[0][1]


def test_no_source_filter_alerts_all(monkeypatch):
    sent = []
    monkeypatch.setattr(alerts_mod, "send_all", lambda *a, **k: sent.append(a) or {})
    _seed_jobs()
    with db_session() as s:
        s.add(SavedSearch(
            name="AlertSrc all",
            query_json={"q": "AlertSrc Engineer"},
            notify=True, notified_job_ids=[],
        ))
    asyncio.run(alerts_mod.check_alerts())
    mine = [a for a in sent if "AlertSrcAcme" in a[1]]
    assert len(mine) == 2


def test_priority_persisted_via_route():
    from fastapi.testclient import TestClient

    from jobhunt.main import app
    client = TestClient(app, base_url="http://127.0.0.1", headers={"origin": "http://127.0.0.1"})
    r = client.post("/alerts/create", data={
        "name": "AlertSrc priority",
        "q": "python",
        "sources": ["wuzzuf", "remotive"],
        "priority": "true",
    }, follow_redirects=False)
    assert r.status_code in (302, 303)
    with db_session() as s:
        ss = s.query(SavedSearch).filter(SavedSearch.name == "AlertSrc priority").one()
        assert ss.query_json.get("priority") is True
        assert set(ss.query_json.get("sources", [])) == {"wuzzuf", "remotive"}
