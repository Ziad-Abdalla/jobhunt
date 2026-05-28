"""Tests for the tech/nontech/other classifier and the /local category filter."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from jobhunt.db import db_session, init_db
from jobhunt.extract import classify_category
from jobhunt.main import app
from jobhunt.models import Job


@pytest.mark.parametrize(
    "title,expected",
    [
        ("Senior Backend Engineer", "tech"),
        ("Software Developer", "tech"),
        ("Frontend Engineer", "tech"),
        ("DevOps Engineer", "tech"),
        ("Cleaner", "nontech"),
        ("Warehouse Operative", "nontech"),
        ("Kitchen Porter", "nontech"),
        ("Retail Assistant", "nontech"),
        ("Customer Service Advisor", "nontech"),
        ("Care Assistant", "nontech"),
        ("Delivery Driver", "nontech"),
        ("Receptionist — Front Desk", "nontech"),
        ("Security Guard", "nontech"),
        ("Marketing Manager", "other"),
        ("CEO", "other"),
    ],
)
def test_classify_title(title: str, expected: str) -> None:
    assert classify_category(title) == expected


def test_classify_description_fallback() -> None:
    # Title is ambiguous ("Assistant"); description tilts it.
    assert classify_category(
        "Assistant",
        "Looking for a kitchen porter to help with dishes and food prep.",
    ) == "nontech"
    assert classify_category(
        "Assistant",
        "Engineer to help build our backend services in Python.",
    ) == "tech"


def _seed(session, **kwargs) -> Job:
    job = Job(
        fingerprint=kwargs["fingerprint"],
        source="findajob",
        source_id=kwargs["fingerprint"],
        url=f"https://example.com/{kwargs['fingerprint']}",
        company=kwargs.get("company", "Acme"),
        title=kwargs["title"],
        location=kwargs.get("location", "London"),
        category=kwargs["category"],
        level=kwargs.get("level", "entry"),
    )
    session.add(job)
    return job


def test_local_route_defaults_to_nontech(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(
        "jobhunt.config.settings.db_path",
        tmp_path / "test.db",
    )
    # Force the engine to rebuild against the temp DB.
    import jobhunt.db as db_mod
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    db_mod._engine = create_engine(f"sqlite:///{tmp_path / 'test.db'}", future=True)
    db_mod._SessionLocal = sessionmaker(bind=db_mod._engine, expire_on_commit=False, future=True)

    init_db()
    with db_session() as s:
        _seed(s, fingerprint="cleaner-london", title="Cleaner",
              location="London", category="nontech")
        _seed(s, fingerprint="dev-london", title="Backend Developer",
              location="London", category="tech")

    client = TestClient(app)
    resp = client.get("/local", params={"location": "London"})
    assert resp.status_code == 200
    body = resp.text
    # Default mode is nontech, so Cleaner should appear and Backend Developer
    # should not show in the cards list.
    assert "Cleaner" in body
    assert "Backend Developer" not in body
    # The category dropdown counts should be present in the page.
    assert "No-experience local work" in body

    # Tech mode explicitly returns tech.
    resp_tech = client.get("/local", params={"location": "London", "category": "tech"})
    assert resp_tech.status_code == 200
    assert "Backend Developer" in resp_tech.text
    assert "Cleaner" not in resp_tech.text

    # Any mode returns both.
    resp_any = client.get("/local", params={"location": "London", "category": "any"})
    assert resp_any.status_code == 200
    assert "Backend Developer" in resp_any.text
    assert "Cleaner" in resp_any.text

    # Cleanup so the next test gets a fresh DB.
    with db_session() as s:
        s.execute(Job.__table__.delete())


def test_local_route_falls_back_to_nontech_on_bad_category() -> None:
    client = TestClient(app)
    resp = client.get("/local", params={"location": "London", "category": "garbage"})
    # Bad values silently coerce to "nontech" — no 5xx.
    assert resp.status_code == 200
