"""Tests for the robustness fixes that landed in v0.10.3 after the
multi-round bug-hunt pass.

Each test names the specific bug it locks down so future contributors
can see the failure mode at a glance."""

from __future__ import annotations

from fastapi.testclient import TestClient

from jobhunt.db import db_session, wal_checkpoint
from jobhunt.main import _MAX_ALERT_FIELD, _MAX_ALERT_NAME, _trim, app
from jobhunt.models import SavedSearch


def test_trim_handles_none_and_long_input() -> None:
    """The shared _trim helper used by /alerts/create — should never raise
    on weird input and always respect the limit."""
    assert _trim("hello", 100) == "hello"
    assert _trim("  hello  ", 100) == "hello"
    assert _trim("hello" * 1000, 10) == "hellohello"
    assert _trim("", 50) == ""
    # None-like via attribute miss — `(s or "")` shields it.
    assert _trim(None, 10) == ""  # type: ignore[arg-type]


def test_alerts_create_truncates_long_name() -> None:
    """Locks down the v0.10.3 fix: a 5000-char alert name was being
    saved verbatim despite the SQLAlchemy String(128) declaration."""
    client = TestClient(app)
    long_name = "n" * 5000
    h = {"Referer": "http://testserver/alerts"}
    # Clean any prior leftover, then post.
    with db_session() as s:
        s.query(SavedSearch).filter(SavedSearch.name.like("n%")).delete()
    r = client.post("/alerts/create", data={"name": long_name, "q": "python"}, headers=h, follow_redirects=False)
    assert r.status_code == 303
    with db_session() as s:
        rows = list(s.query(SavedSearch).filter(SavedSearch.name.like("n%")).all())
    assert len(rows) == 1
    assert len(rows[0].name) == _MAX_ALERT_NAME, (
        f"expected name truncated to {_MAX_ALERT_NAME}, got {len(rows[0].name)}"
    )
    with db_session() as s:
        s.query(SavedSearch).filter(SavedSearch.name == rows[0].name).delete()


def test_alerts_create_truncates_free_text_fields() -> None:
    """Locks down: a 5000-char `q` or `location` was bloating the JSON
    row. Cap is _MAX_ALERT_FIELD per field."""
    client = TestClient(app)
    h = {"Referer": "http://testserver/alerts"}
    with db_session() as s:
        s.query(SavedSearch).filter(SavedSearch.name == "long-q-test").delete()
    r = client.post(
        "/alerts/create",
        data={
            "name": "long-q-test",
            "q": "x" * 5000,
            "location": "y" * 5000,
        },
        headers=h,
        follow_redirects=False,
    )
    assert r.status_code == 303
    with db_session() as s:
        row = s.query(SavedSearch).filter(SavedSearch.name == "long-q-test").one()
    assert len(row.query_json["q"]) <= _MAX_ALERT_FIELD
    assert len(row.query_json["location"]) <= _MAX_ALERT_FIELD
    with db_session() as s:
        s.query(SavedSearch).filter(SavedSearch.name == "long-q-test").delete()


def test_wal_checkpoint_never_raises() -> None:
    """Called on every refresh; must be a strict no-op when something
    else holds the WAL — never raise."""
    wal_checkpoint()  # should just return cleanly
