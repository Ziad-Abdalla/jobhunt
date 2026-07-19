"""Tests for the auto-disable mechanism: a source that has failed 3 scrapes
in a row should be skipped on the next refresh, and surface in the
/api/sources/health summary.

Each test uses a `cleanup` autouse fixture that scrubs the test sources
both before and after, so a previous failure leaving rows behind never
affects the next run.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient

from jobhunt.db import db_session, init_db
from jobhunt.main import app
from jobhunt.models import ScrapeRun
from jobhunt.refresh import _AUTO_DISABLE_AFTER, _disabled_sources, _retry_due

_TEST_SOURCES = (
    "test-broken", "test-half-broken", "test-flaky", "test-silent",
)


@pytest.fixture(autouse=True)
def _cleanup_test_sources():
    """Wipe any leftover test rows before AND after each test so pollution
    from a prior failure can't make the next run flaky."""
    init_db()
    with db_session() as s:
        s.query(ScrapeRun).filter(ScrapeRun.source.in_(_TEST_SOURCES)).delete()
    yield
    with db_session() as s:
        s.query(ScrapeRun).filter(ScrapeRun.source.in_(_TEST_SOURCES)).delete()


def _seed_runs(session, source: str, board: str, n: int,
               jobs_seen: int = 0, error: str | None = "fail",
               start_offset_days: int = 0) -> None:
    """Append n scrape_runs at increasing timestamps. start_offset_days
    lets a test mix old + new seed rows in a deterministic order."""
    base = datetime.now(UTC) - timedelta(days=n + start_offset_days)
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
    with db_session() as s:
        _seed_runs(s, "test-broken", "co", n=_AUTO_DISABLE_AFTER, error="HTTPError 404")
    with db_session() as s:
        disabled = _disabled_sources(s)
    assert ("test-broken", "co") in disabled


def test_not_disabled_with_fewer_failures() -> None:
    with db_session() as s:
        _seed_runs(s, "test-half-broken", "co",
                   n=_AUTO_DISABLE_AFTER - 1, error="HTTPError 404")
    with db_session() as s:
        disabled = _disabled_sources(s)
    assert ("test-half-broken", "co") not in disabled


def test_not_disabled_when_any_recent_run_succeeded() -> None:
    """A single success in the recent window re-enables the source."""
    with db_session() as s:
        # 2 old failures, then 1 recent success.
        _seed_runs(s, "test-flaky", "co", n=2,
                   error="HTTPError 503", start_offset_days=5)
        _seed_runs(s, "test-flaky", "co", n=1,
                   jobs_seen=42, error=None, start_offset_days=0)
    with db_session() as s:
        disabled = _disabled_sources(s)
    assert ("test-flaky", "co") not in disabled


def test_disabled_when_zero_jobs_no_error() -> None:
    """3 consecutive zero-job runs (no exception) is still 'silent decay'
    and triggers auto-disable — the more dangerous failure mode."""
    with db_session() as s:
        _seed_runs(s, "test-silent", "co",
                   n=_AUTO_DISABLE_AFTER, jobs_seen=0, error=None)
    with db_session() as s:
        disabled = _disabled_sources(s)
    assert ("test-silent", "co") in disabled


def test_retry_due_true_when_last_attempt_is_stale() -> None:
    now = datetime.now(UTC)
    assert _retry_due(now - timedelta(hours=25), now, 24.0) is True


def test_retry_due_false_when_last_attempt_is_recent() -> None:
    now = datetime.now(UTC)
    assert _retry_due(now - timedelta(hours=1), now, 24.0) is False


def test_retry_due_handles_naive_datetime_as_utc() -> None:
    # Datetimes read back from SQLite are naive; _retry_due must not crash on them.
    now = datetime.now(UTC)
    naive_stale = (now - timedelta(hours=48)).replace(tzinfo=None)
    assert _retry_due(naive_stale, now, 24.0) is True


def test_disabled_sources_reports_last_attempt_time() -> None:
    """scrape_all needs the last attempt time per disabled source to decide when to
    retry it — so a permanently-skipped source can self-heal."""
    with db_session() as s:
        _seed_runs(s, "test-broken", "co", n=_AUTO_DISABLE_AFTER, error="404")
    with db_session() as s:
        disabled = _disabled_sources(s)
    key = ("test-broken", "co")
    assert key in disabled  # membership still works (dict keys)
    assert isinstance(disabled[key], datetime)


def test_long_dead_source_is_retry_due_so_it_can_self_heal() -> None:
    """A source disabled by OLD failures is due for a re-attempt (records a fresh
    run that can clear the disable) — this is the self-heal the old code lacked."""
    with db_session() as s:
        _seed_runs(s, "test-broken", "co", n=_AUTO_DISABLE_AFTER,
                   error="404", start_offset_days=10)
    with db_session() as s:
        disabled = _disabled_sources(s)
    key = ("test-broken", "co")
    assert key in disabled
    assert _retry_due(disabled[key], datetime.now(UTC), 24.0) is True


def test_sources_health_endpoint() -> None:
    """JSON shape contract for the Settings-page badge + skill."""
    client = TestClient(app)
    r = client.get("/api/sources/health")
    assert r.status_code == 200
    body = r.json()
    assert set(body.keys()) == {"offline", "attention", "total"}
    assert all(isinstance(body[k], int) for k in body)


def test_settings_page_shows_sources_section() -> None:
    client = TestClient(app)
    r = client.get("/settings")
    assert r.status_code == 200
    assert ">Sources<" in r.text
