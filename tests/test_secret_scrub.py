"""Audit HIGH-2: a leaked API key in a scraper error must be scrubbed before
it reaches logs / scrape_runs.error / /api/sources/health."""

from __future__ import annotations

from jobhunt.config import settings
from jobhunt.refresh import _scrub_secrets


def test_scrubs_jooble_key(monkeypatch):
    monkeypatch.setattr(settings, "jooble_api_key", "SECRETKEY123")
    err = ("HTTPStatusError: Server error '500' for url "
           "'https://jooble.org/api/SECRETKEY123'")
    out = _scrub_secrets(err)
    assert "SECRETKEY123" not in out
    assert "***REDACTED***" in out


def test_scrubs_reed_key(monkeypatch):
    monkeypatch.setattr(settings, "reed_api_key", "reedkey-abc")
    assert "reedkey-abc" not in _scrub_secrets("auth failed for reedkey-abc")


def test_no_key_configured_is_noop(monkeypatch):
    monkeypatch.setattr(settings, "jooble_api_key", "")
    monkeypatch.setattr(settings, "reed_api_key", "")
    msg = "ConnectError: connection refused"
    assert _scrub_secrets(msg) == msg
