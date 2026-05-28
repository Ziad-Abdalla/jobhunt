"""Tests for the keyword-fallback CV mode.

These run regardless of whether sentence-transformers is installed.
"""

from __future__ import annotations

from jobhunt.cv import keyword_score


def test_keyword_score_exact_match() -> None:
    score = keyword_score(
        cv_skills=["aws", "kubernetes"],
        cv_languages=["python", "go"],
        job_skills=["aws", "kubernetes"],
        job_languages=["python"],
    )
    assert score > 0.5  # strong overlap


def test_keyword_score_no_overlap() -> None:
    score = keyword_score(
        cv_skills=["aws"],
        cv_languages=["python"],
        job_skills=["azure"],
        job_languages=["java"],
    )
    assert score == 0.0


def test_keyword_score_empty_cv() -> None:
    score = keyword_score(
        cv_skills=[],
        cv_languages=[],
        job_skills=["aws"],
        job_languages=["python"],
    )
    assert score == 0.0


def test_keyword_score_empty_job() -> None:
    score = keyword_score(
        cv_skills=["aws"],
        cv_languages=["python"],
        job_skills=[],
        job_languages=[],
    )
    assert score == 0.0


def test_keyword_score_language_weighted() -> None:
    """Language matches are worth more than skill matches."""
    only_lang = keyword_score(
        cv_skills=[], cv_languages=["python"],
        job_skills=[], job_languages=["python"],
    )
    only_skill = keyword_score(
        cv_skills=["aws"], cv_languages=[],
        job_skills=["aws"], job_languages=[],
    )
    # Language-only match scores >= skill-only match in jaccard with language
    # weight 2x.
    assert only_lang >= only_skill
