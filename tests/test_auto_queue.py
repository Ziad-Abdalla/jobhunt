"""P-B auto-queue: saved-search scope, ordering, skip rules, cap, gating."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from jobhunt import auto_queue as aq
from jobhunt.cowork_models import Application
from jobhunt.db import db_session, init_db
from jobhunt.models import CVProfile, Job, SavedSearch

_TEST_COMPANY_A = "AutoQueueAcme"
_TEST_COMPANY_B = "AutoQueueBeta"
_COMPANIES = (_TEST_COMPANY_A, _TEST_COMPANY_B)


def _clean() -> None:
    with db_session() as s:
        ids = [j.id for j in s.query(Job).filter(Job.company.in_(_COMPANIES))]
        if ids:
            s.query(Application).filter(Application.job_id.in_(ids)).delete()
        s.query(Job).filter(Job.company.in_(_COMPANIES)).delete()
        s.query(SavedSearch).filter(SavedSearch.name.like("autoq-%")).delete()


@pytest.fixture(autouse=True)
def _setup(monkeypatch):
    init_db()
    _clean()
    monkeypatch.setattr(aq.settings, "auto_queue", True)
    monkeypatch.setattr(aq.settings, "auto_queue_daily_cap", 0)
    monkeypatch.setattr(aq.settings, "auto_queue_company_cooldown_days", 14)
    yield
    _clean()


def _add_job(n: int, *, company: str = _TEST_COMPANY_A, title: str = "Python Dev",
             category: str = "tech", skills: list[str] | None = None) -> int:
    with db_session() as s:
        s.add(Job(
            fingerprint=f"autoq-{n}-" + "x" * 20, source="test-aq",
            source_id=f"aq{n}", url=f"https://example.com/{n}",
            company=company, title=f"{title} {n}",
            description="autoqueue fixture python role", category=category,
            skills=skills if skills is not None else ["python"], score=1.0,
        ))
    with db_session() as s:
        return s.query(Job).filter(Job.source_id == f"aq{n}",
                                   Job.company.in_(_COMPANIES)).one().id


def _add_search(q: str = "autoqueue fixture") -> None:
    with db_session() as s:
        s.add(SavedSearch(name="autoq-test", query_json={"q": q}))


def _add_cv() -> None:
    with db_session() as s:
        cv = s.get(CVProfile, 1)
        if cv is None:
            cv = CVProfile(id=1)
            s.add(cv)
        cv.detected_skills = ["python"]


def test_off_by_default(monkeypatch):
    monkeypatch.setattr(aq.settings, "auto_queue", False)
    out = aq.auto_queue_pass()
    assert out == {"queued": 0, "skipped_existing": 0,
                   "skipped_cooldown": 0, "skipped_category": 0}


def test_queues_saved_search_matches_marked_auto():
    _add_cv()
    _add_search()
    _add_job(1)
    _add_job(2, company=_TEST_COMPANY_B)
    out = aq.auto_queue_pass()
    assert out["queued"] == 2
    with db_session() as s:
        ids = [j.id for j in s.query(Job).filter(Job.company.in_(_COMPANIES))]
        rows = s.query(Application).filter(Application.job_id.in_(ids)).all()
        assert len(rows) == 2
        assert all(a.queued_by == "auto" and a.status == "queued" for a in rows)


def test_skips_jobs_with_existing_application_any_status():
    _add_cv()
    _add_search()
    jid = _add_job(1)
    with db_session() as s:
        s.add(Application(job_id=jid, status="rejected"))
    out = aq.auto_queue_pass()
    assert out["queued"] == 0
    assert out["skipped_existing"] == 1


def test_company_cooldown():
    _add_cv()
    _add_search()
    jid1 = _add_job(1)
    _add_job(2)  # same company
    with db_session() as s:
        s.add(Application(job_id=jid1, status="submitted",
                          created_at=datetime.now(UTC)))
    out = aq.auto_queue_pass()
    assert out["queued"] == 0
    assert out["skipped_cooldown"] >= 1


def test_category_mismatch_floor():
    _add_cv()
    _add_search()
    _add_job(1, category="nontech", skills=["forklift"])
    out = aq.auto_queue_pass()
    assert out["queued"] == 0
    assert out["skipped_category"] == 1


def test_nontech_with_skill_overlap_allowed():
    _add_cv()
    _add_search()
    _add_job(1, category="nontech", skills=["python"])
    out = aq.auto_queue_pass()
    assert out["queued"] == 1


def test_daily_cap(monkeypatch):
    monkeypatch.setattr(aq.settings, "auto_queue_daily_cap", 1)
    _add_cv()
    _add_search()
    _add_job(1)
    _add_job(2, company=_TEST_COMPANY_B)
    out = aq.auto_queue_pass()
    assert out["queued"] == 1


def test_source_filter_respected():
    _add_cv()
    with db_session() as s:
        s.add(SavedSearch(name="autoq-test",
                          query_json={"q": "autoqueue fixture",
                                      "sources": ["some-other-source"]}))
    _add_job(1)
    out = aq.auto_queue_pass()
    assert out["queued"] == 0
