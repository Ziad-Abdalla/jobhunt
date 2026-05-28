"""Tests for the FTS5 full-text-search code path.

FTS5 is the default when the SQLite build supports it; LIKE remains the
fallback. These tests exercise both routes via the helper functions, plus
an integration check that a real /api/jobs?q=… query returns results.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from jobhunt.db import db_session, has_fts5, init_db
from jobhunt.filters import JobQuery, _fts_query, search
from jobhunt.main import app
from jobhunt.models import Job


def test_fts_query_strips_metacharacters() -> None:
    """User input must not be able to inject FTS5 operators."""
    assert _fts_query("python") == '"python"'
    assert _fts_query("python developer") == '"python" "developer"'
    # FTS5 operators (- : ^) must be stripped, not interpreted.
    assert _fts_query("python -django") == '"python" "django"'
    assert _fts_query("OR AND NOT") == '"OR" "AND" "NOT"'
    # Empty / whitespace-only → None so caller falls back to LIKE-or-nothing.
    assert _fts_query("") is None
    assert _fts_query("   ") is None
    # Single-char terms are dropped (FTS5 noise).
    assert _fts_query("a b c++") == '"c++"'


def test_fts_handles_unicode() -> None:
    """Non-ASCII terms (München, naïve) must survive cleaning."""
    out = _fts_query("müncheN naïve")
    assert out is not None
    assert "münche" in out.lower()


@pytest.mark.skipif(not has_fts5(), reason="SQLite build lacks FTS5")
def test_fts_search_finds_seeded_job() -> None:
    """End-to-end: seed a job, query via /api/jobs?q=, FTS5 path returns it."""
    init_db()
    with db_session() as s:
        s.query(Job).filter(Job.fingerprint == "fts-test-1").delete()
        s.add(Job(
            fingerprint="fts-test-1",
            source="test",
            source_id="fts-1",
            url="https://example.com/fts-1",
            company="Acme Corp",
            title="Senior Python Engineer",
            location="Remote",
            description="We're looking for a Python engineer with FastAPI experience.",
        ))
    # Use a tag unique to this test so we don't compete with the 24k real
    # rows that also match "python engineer".
    with db_session() as s:
        s.query(Job).filter(Job.fingerprint == "fts-test-1").delete()
        s.add(Job(
            fingerprint="fts-test-1",
            source="test",
            source_id="fts-1",
            url="https://example.com/fts-1",
            company="Acme Corp",
            title="ZZQQX Test Sentinel",
            location="Remote",
            description="A unique zzqqx sentinel string for FTS5 testing.",
        ))
    client = TestClient(app)
    r = client.get("/api/jobs", params={"q": "zzqqx"})
    assert r.status_code == 200
    titles = [j["title"] for j in r.json()["results"]]
    assert any("ZZQQX" in t for t in titles)
    # Cleanup
    with db_session() as s:
        s.query(Job).filter(Job.fingerprint == "fts-test-1").delete()


def test_fts_query_does_not_5xx_on_garbage() -> None:
    """Any user input (special chars, SQL-injection-flavoured strings,
    long noise) must produce a 200 response, never a 500."""
    client = TestClient(app)
    payloads = [
        "'; DROP TABLE jobs; --",
        '"unterminated string',
        "NEAR(",
        "AND OR NOT",
        "x" * 500,
        "🚀🎯",
        "../etc/passwd",
    ]
    for p in payloads:
        r = client.get("/api/jobs", params={"q": p})
        assert r.status_code == 200, f"500 on q={p!r}"


def test_fts_search_function_directly() -> None:
    """Calling search() via the helper exercises the same path the API
    uses. Confirms it returns a list without raising."""
    init_db()
    with db_session() as s:
        rows = search(s, JobQuery(q="developer", limit=5))
    assert isinstance(rows, list)
