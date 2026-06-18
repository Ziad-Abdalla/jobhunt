"""The Refresh button must not block on the full scrape: /api/refresh kicks
the work off in the background and returns immediately, and /api/refresh/status
reports progress."""

from __future__ import annotations

import jobhunt.main as m
from fastapi.testclient import TestClient


def test_refresh_starts_in_background_and_returns_immediately(monkeypatch):
    async def fast_scrape():
        return {"sources": 1, "added": 0, "seen": 0, "removed": 0}

    async def no_alerts():
        return {"notified": 0}

    monkeypatch.setattr(m, "scrape_all", fast_scrape)
    monkeypatch.setattr(m, "check_alerts", no_alerts)
    m._last_refresh.clear()
    m._scrape_state.update(running=False, started_at=0.0, last=None)

    client = TestClient(app=m.app)
    r = client.post("/api/refresh")
    assert r.status_code == 200
    j = r.json()
    # Non-blocking: it reports the scrape was started rather than returning the
    # finished result.
    assert j["ok"] is True
    assert j["running"] is True


def test_refresh_status_endpoint_exists(monkeypatch):
    m._scrape_state.update(running=False, started_at=0.0, last={"added": 7})
    client = TestClient(app=m.app)
    s = client.get("/api/refresh/status")
    assert s.status_code == 200
    body = s.json()
    assert "running" in body
    assert "last" in body
