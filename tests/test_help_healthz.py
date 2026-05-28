"""Tests for the new /help page and richer /api/healthz."""

from __future__ import annotations

from fastapi.testclient import TestClient

from jobhunt.main import app


def test_help_page_renders() -> None:
    client = TestClient(app)
    r = client.get("/help")
    assert r.status_code == 200
    body = r.text
    # Key sections must be present.
    for heading in ["Getting started", "Filters explained", "API keys",
                    "Updates", "Troubleshooting", "Privacy"]:
        assert heading in body


def test_help_has_skip_link() -> None:
    """Accessibility minimum: a 'Skip to main content' link reachable via
    keyboard for screen reader users."""
    client = TestClient(app)
    r = client.get("/help")
    assert "Skip to main content" in r.text
    assert 'href="#main"' in r.text


def test_help_in_nav() -> None:
    """The Help link should appear in the navigation so users can find
    it without knowing the URL."""
    client = TestClient(app)
    r = client.get("/")
    assert 'href="/help"' in r.text


def test_healthz_returns_stats() -> None:
    client = TestClient(app)
    r = client.get("/api/healthz")
    assert r.status_code == 200
    data = r.json()
    # Existing contract.
    assert data["ok"] is True
    assert "version" in data
    # New operational stats.
    assert "jobs" in data and isinstance(data["jobs"], int)
    assert "sources" in data and set(data["sources"]) == {"offline", "attention", "total"}
    assert "last_refresh" in data  # may be null
    assert "db_bytes" in data and isinstance(data["db_bytes"], int)
