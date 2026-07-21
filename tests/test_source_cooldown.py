"""Per-source scrape cooldown for quota-capped sources (jsearch).

jsearch's free tier is ~200 req/month and every configured board costs one
request per pass — an unattended 6-hour scheduler over 6 boards would burn
~3.6x the monthly quota. The cooldown skips quota-capped sources on a full
refresh until `jsearch_cooldown_hours` have passed since the last attempt;
an explicit only_sources request naming the source bypasses it (deliberate
targeted run). Priority fast-poll sets must never include a quota-capped
source, so collect_priority_sources drops them.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from jobhunt.config import settings
from jobhunt.db import db_session, init_db
from jobhunt.models import SavedSearch, ScrapeRun
from jobhunt.refresh import _apply_cooldown, _last_attempts

_TEST_SOURCE = "test-cooldown"
_TEST_SEARCH = "test-cooldown-priority"


@pytest.fixture(autouse=True)
def _cleanup():
    init_db()
    with db_session() as s:
        s.query(ScrapeRun).filter(ScrapeRun.source == _TEST_SOURCE).delete()
        s.query(SavedSearch).filter(SavedSearch.name == _TEST_SEARCH).delete()
    yield
    with db_session() as s:
        s.query(ScrapeRun).filter(ScrapeRun.source == _TEST_SOURCE).delete()
        s.query(SavedSearch).filter(SavedSearch.name == _TEST_SEARCH).delete()


def test_settings_has_jsearch_cooldown_default():
    assert settings.jsearch_cooldown_hours == 20.0


def test_last_attempts_returns_latest_started_at():
    now = datetime.now(UTC)
    with db_session() as s:
        for hours_ago in (30, 2):
            s.add(ScrapeRun(
                source=_TEST_SOURCE, board="a|b",
                started_at=now - timedelta(hours=hours_ago),
                finished_at=now - timedelta(hours=hours_ago, minutes=-1),
                jobs_seen=1, jobs_added=0, jobs_removed=0, error=None,
            ))
    with db_session() as s:
        last = _last_attempts(s, {_TEST_SOURCE})
    assert _TEST_SOURCE in last
    # Naive-vs-aware: SQLite reads back naive; compare after normalizing.
    got = last[_TEST_SOURCE]
    if got.tzinfo is None:
        got = got.replace(tzinfo=UTC)
    assert abs((got - (now - timedelta(hours=2))).total_seconds()) < 60


def test_last_attempts_empty_when_no_history():
    with db_session() as s:
        assert _last_attempts(s, {_TEST_SOURCE}) == {}


def _specs():
    return [
        {"source": "jsearch", "board": "developer|Egypt"},
        {"source": "jsearch", "board": "AI engineer|remote"},
        {"source": "wuzzuf", "board": ""},
    ]


def test_cooldown_skips_recent_quota_source():
    now = datetime.now(UTC)
    kept, skipped = _apply_cooldown(
        _specs(),
        cooldowns={"jsearch": 20.0},
        last_attempts={"jsearch": now - timedelta(hours=2)},
        now=now,
    )
    assert skipped == 2
    assert [s["source"] for s in kept] == ["wuzzuf"]


def test_cooldown_allows_stale_quota_source():
    now = datetime.now(UTC)
    kept, skipped = _apply_cooldown(
        _specs(),
        cooldowns={"jsearch": 20.0},
        last_attempts={"jsearch": now - timedelta(hours=21)},
        now=now,
    )
    assert skipped == 0
    assert len(kept) == 3


def test_cooldown_allows_first_ever_run():
    kept, skipped = _apply_cooldown(
        _specs(),
        cooldowns={"jsearch": 20.0},
        last_attempts={},
        now=datetime.now(UTC),
    )
    assert skipped == 0
    assert len(kept) == 3


def test_explicit_only_sources_bypasses_cooldown():
    """A deliberate targeted run (e.g. the live-probe path
    scrape_all(only_sources={'jsearch'})) is never silently no-opped."""
    now = datetime.now(UTC)
    kept, skipped = _apply_cooldown(
        _specs(),
        cooldowns={"jsearch": 20.0},
        last_attempts={"jsearch": now - timedelta(hours=1)},
        now=now,
        only_sources={"jsearch"},
    )
    assert skipped == 0
    assert len(kept) == 3


def test_disabled_cooldown_is_inert():
    now = datetime.now(UTC)
    kept, skipped = _apply_cooldown(
        _specs(),
        cooldowns={"jsearch": 0.0},
        last_attempts={"jsearch": now - timedelta(hours=1)},
        now=now,
    )
    assert skipped == 0
    assert len(kept) == 3


def test_priority_sources_exclude_quota_capped():
    """A priority saved search listing jsearch must NOT put jsearch on the
    fast-poll tier — that would re-spend the monthly quota every tick."""
    from jobhunt.alerts import collect_priority_sources

    with db_session() as s:
        s.add(SavedSearch(
            name=_TEST_SEARCH,
            query_json={"q": "x", "sources": ["jsearch", "wuzzuf"], "priority": True},
            notify=True,
            notified_job_ids=[],
        ))
    out = collect_priority_sources()
    assert "jsearch" not in out
    assert "wuzzuf" in out
