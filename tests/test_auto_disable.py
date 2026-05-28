"""Tests for the auto-disable mechanism: a source that has failed 3 scrapes
in a row should be skipped on the next refresh, and surface in the
/api/sources/health summary."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from fastapi.testclient import TestClient

from jobhunt.db import db_session, init_db
from jobhunt.main import app
from jobhunt.models import ScrapeRun
from jobhunt.refresh import _AUTO_DISABLE_AFTER, _disabled_sources


def _seed_runs(session, source: str, board: str, n: int,
               jobs_seen: int = 0, error: str | None = "fail") -> None:
    """Append n scrape_runs for (source, board) at increasing timestamps."""
    base = datetime.now(UTC) - timedelta(days=n)
    for i in range(n):
        session.add(ScrapeRun(
            source=source,
            board=board,
            started_at=base + timedelta(hours=i),
            finished_at=base + timedelta(hours=i, minutes=1),
            jobs_seen=jobs_seen,
            jobs_added=0,
            jobs_removed=0,
            error=error,
        ))


def test_disabled_after_three_consecutive_failures() -> None:
    init_db()
    with db_session() as s:
        s.query(ScrapeRun).filter(ScrapeRun.source == "test-broken").delete()
        _seed_runs(s, "test-broken", "co", n=_AUTO_DISABLE_AFTER, error="HTTPError 404")
    with db_session() as s:
        disabled = _disabled_sources(s)
    assert ("test-broken", "co") in disabled
    with db_session() as s:
        s.query(ScrapeRun).filter(ScrapeRun.source == "test-broken").delete()


def test_not_disabled_with_fewer_failures() -> None:
    init_db()
    with db_session() as s:
        s.query(ScrapeRun).filter(ScrapeRun.source == "test-half-broken").delete()
        _seed_runs(s, "test-half-broken", "co",
                   n=_AUTO_DISABLE_AFTER - 1, error="HTTPError 404")
    with db_session() as s:
        disabled = _disabled_sources(s)
    assert ("test-half-broken", "co") not in disabled
    with db_session() as s:
        s.query(ScrapeRun).filter(ScrapeRun.source == "test-half-broken").delete()


def test_not_disabled_when_any_recent_run_succeeded() -> None:
    """A single success in the recent window re-enables the source."""
    init_db()
    with db_session() as s:
        s.query(ScrapeRun).filter(ScrapeRun.source == "test-flaky").delete()
        _seed_runs(s, "test-flaky", "co", n=2, error="HTTPError 503")
        _seed_runs(s, "test-flaky", "co", n=1, jobs_seen=42, error=None)
    with db_session() as s:
        disabled = _disabled_sources(s)
    assert ("test-flaky", "co") not in disabled
    with db_session() as s:
        s.query(ScrapeRun).filter(ScrapeRun.source == "test-flaky").delete()


def test_disabled_when_zero_jobs_no_error() -> None:
    """A scraper that returns 0 jobs for 3 consecutive runs gets disabled —
    silent decay is the more dangerous mode."""
    init_db()
    with db_session() as s:
        s.query(ScrapeRun).filter(ScrapeRun.source == "test-silent").delete()
        _seed_runs(s, "test-silent", "co",
                   n=_AUTO_DISABLE_AFTER, jobs_seen=0, error=None)
    with db_session() as s:
        disabled = _disabled_sources(s)
    assert ("test-silent", "co") in disabled
    with db_session() as s:
        s.query(ScrapeRun).filter(ScrapeRun.source == "test-silent").delete()


def test_sources_health_endpoint() -> None:
    """The /api/sources/health endpoint returns the offline/attention/total
    summary the Settings page badge uses."""
    client = TestClient(app)
    r = client.get("/api/sources/health")
    assert r.status_code == 200
    body = r.json()
    assert set(body.keys()) == {"offline", "attention", "total"}
    assert all(isinstance(body[k], int) for k in body)


def test_settings_page_shows_sources_section() -> None:
    """The Settings page renders the new Sources section."""
    client = TestClient(app)
    r = client.get("/settings")
    assert r.status_code == 200
    assert ">Sources<" in r.text
