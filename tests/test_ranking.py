"""P4: ordering tests for the reachability/CV-blended rank expression.

Runs against the dev DB like the rest of the suite: every row is seeded
with company='P4RankProbeCo' + fingerprint prefix 'p4rank-' and removed in
teardown; searches filter on that company so real rows never interfere.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from jobhunt.db import db_session, init_db
from jobhunt.filters import JobQuery, search
from jobhunt.models import Job

COMPANY = "P4RankProbeCo"


def _seed(jobs: list[dict]) -> None:
    with db_session() as s:
        for spec in jobs:
            s.add(Job(
                fingerprint=f"p4rank-{spec['id']}",
                source="test",
                source_id=f"p4rank-{spec['id']}",
                url=f"https://example.com/p4rank/{spec['id']}",
                company=COMPANY,
                title=spec.get("title", f"Role {spec['id']}"),
                location="Remote",
                description="p4 ranking probe",
                score=spec.get("score", 0.0),
                cv_match=spec.get("cv_match"),
                geo_restrict=spec.get("geo_restrict", "unknown"),
                posted_at=spec.get("posted_at"),
            ))


@pytest.fixture(autouse=True)
def _clean_probe_rows():
    init_db()

    def wipe() -> None:
        with db_session() as s:
            s.query(Job).filter(Job.company == COMPANY).delete()

    wipe()
    yield
    wipe()


def _order(sort: str, home_region: str = "") -> list[str]:
    q = JobQuery(company=COMPANY, sort=sort, home_region=home_region)
    with db_session() as s:
        return [j.source_id.removeprefix("p4rank-") for j in search(s, q)]


def test_default_sort_blends_cv_match() -> None:
    # B: lower quality score but strong CV match -> 1.5*(1+1.5*0.9)=3.52
    # beats A's 2.0. With no CV signal A would win.
    _seed([
        {"id": "a", "score": 2.0, "cv_match": None},
        {"id": "b", "score": 1.5, "cv_match": 0.9},
    ])
    assert _order("score") == ["b", "a"]


def test_default_sort_unchanged_when_no_cv_and_no_home() -> None:
    _seed([
        {"id": "a", "score": 2.0, "cv_match": None},
        {"id": "b", "score": 1.5, "cv_match": None},
    ])
    assert _order("score") == ["a", "b"]


def test_unreachable_geo_sinks_for_foreign_user_only() -> None:
    # B is better quality but us-only; an 'other' (e.g. Egypt) user sees A
    # first (1.0 vs 1.2*0.35=0.42); a US user and an unknown-home user see B.
    _seed([
        {"id": "a", "score": 1.0, "geo_restrict": "unrestricted"},
        {"id": "b", "score": 1.2, "geo_restrict": "us-only"},
    ])
    assert _order("score", home_region="other") == ["a", "b"]
    assert _order("score", home_region="us") == ["b", "a"]
    assert _order("score", home_region="") == ["b", "a"]


def test_conservative_buckets_never_penalized() -> None:
    _seed([
        {"id": "a", "score": 1.0, "geo_restrict": "unrestricted"},
        {"id": "b", "score": 1.2, "geo_restrict": "restricted-other"},
        {"id": "c", "score": 1.1, "geo_restrict": "unknown"},
    ])
    assert _order("score", home_region="other") == ["b", "c", "a"]


def test_posted_sort_ignores_cv_and_geo() -> None:
    now = datetime.now(UTC)
    _seed([
        {"id": "old", "score": 3.0, "cv_match": 0.9, "geo_restrict": "unrestricted",
         "posted_at": now - timedelta(days=10)},
        {"id": "new", "score": 0.5, "cv_match": 0.0, "geo_restrict": "us-only",
         "posted_at": now},
    ])
    assert _order("posted", home_region="other") == ["new", "old"]


def test_cv_sort_applies_reach_weight() -> None:
    # Egypt user: 0.5 unrestricted beats 0.8*0.35=0.28 us-only; unknown home
    # keeps the raw cv order.
    _seed([
        {"id": "a", "score": 1.0, "cv_match": 0.8, "geo_restrict": "us-only"},
        {"id": "b", "score": 1.0, "cv_match": 0.5, "geo_restrict": "unrestricted"},
    ])
    assert _order("cv", home_region="other") == ["b", "a"]
    assert _order("cv", home_region="") == ["a", "b"]


def test_cv_sort_null_matches_rank_last() -> None:
    _seed([
        {"id": "a", "score": 5.0, "cv_match": None},
        {"id": "b", "score": 0.1, "cv_match": 0.2},
    ])
    assert _order("cv") == ["b", "a"]


def test_cv_sort_null_ties_with_zero_score_breaks() -> None:
    # DELIBERATE post-P4 behavior (review-pinned): NULL and explicit 0.0 both
    # coalesce to 0 in the cv sort; the higher-quality job wins the tie.
    # Pre-P4 nullslast put the explicit 0.0 first.
    _seed([
        {"id": "a", "score": 5.0, "cv_match": None},
        {"id": "c", "score": 1.0, "cv_match": 0.0},
    ])
    assert _order("cv") == ["a", "c"]


def test_multiplicative_blend_strands_zero_score_jobs() -> None:
    # DELIBERATE property (review-pinned): the blend multiplies the quality
    # score, so score=0 stays rank 0 even at cv_match=1.0. Such jobs remain
    # findable via sort=cv.
    _seed([
        {"id": "a", "score": 0.0, "cv_match": 1.0},
        {"id": "b", "score": 0.5, "cv_match": 0.0},
    ])
    assert _order("score") == ["b", "a"]
    assert _order("cv") == ["a", "b"]


def test_query_from_request_fills_home_region(monkeypatch) -> None:
    from jobhunt import main as main_mod
    from jobhunt.scoring import home_region_from_location

    home_region_from_location.cache_clear()
    monkeypatch.setattr(main_mod.settings, "user_location", "Cairo, Egypt")
    q = main_mod._query_from_request(
        "", "", "", "", "", "", None, [], [], None, "score", 50, 0,
    )
    assert q.home_region == "other"

    home_region_from_location.cache_clear()
    monkeypatch.setattr(main_mod.settings, "user_location", "")
    q = main_mod._query_from_request(
        "", "", "", "", "", "", None, [], [], None, "score", 50, 0,
    )
    assert q.home_region == ""
    home_region_from_location.cache_clear()
