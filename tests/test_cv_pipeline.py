"""End-to-end CV pipeline tests.

Generates three sample CVs (junior Python dev, senior ML engineer, frontend React),
runs them through the full upload → embed → match pipeline against a small synthetic
job corpus, and asserts that the top match for each CV is in the expected role family.

Skipped automatically if sentence-transformers is not installed.
"""

from __future__ import annotations

import os

import pytest

# Skip the whole module if the [match] extra isn't present.
pytest.importorskip("sentence_transformers")

from jobhunt.cv import (  # noqa: E402
    clear_cv,
    cosine,
    cv_status,
    embed_text,
    match_all_jobs,
    parse_cv,
    upload_cv,
)
from jobhunt.db import db_session, init_db  # noqa: E402
from jobhunt.models import Job  # noqa: E402


JUNIOR_PY_CV = """
Alex Morgan
Junior Software Engineer

EXPERIENCE
Acme Web — Junior Backend Developer (2024–present)
- Built REST APIs in Python with FastAPI and PostgreSQL
- Wrote unit tests with pytest, deployed via Docker
- Implemented authentication with JWT, integrated Stripe webhooks

EDUCATION
BSc Computer Science, University of Manchester (2024)

SKILLS
Python, FastAPI, Django, PostgreSQL, Docker, Git, Linux, pytest, REST APIs
"""

SENIOR_ML_CV = """
Dr. Priya Shah
Senior Machine Learning Engineer

EXPERIENCE
DeepGrid AI — Senior ML Engineer (2021–present)
- Architected production training pipelines for LLMs and vision models
- 8 years of experience deploying PyTorch and TensorFlow models at scale
- Led a team building retrieval-augmented generation systems
- Optimized inference with CUDA kernels, ONNX, TensorRT

EDUCATION
PhD Machine Learning, ETH Zurich (2018)
MSc Computer Science, IIT Bombay (2014)

SKILLS
Python, PyTorch, TensorFlow, CUDA, distributed systems, transformers,
deep learning, MLOps, Kubernetes, AWS SageMaker, retrieval augmented generation
"""

FRONTEND_REACT_CV = """
Jordan Lee
Frontend Engineer

EXPERIENCE
Pixelcraft Studio — Frontend Engineer (2022–present)
- Built responsive React applications with Next.js and TypeScript
- 4 years of experience designing accessible component libraries
- Implemented design systems with Storybook and Tailwind CSS
- Optimized Core Web Vitals; reduced LCP by 40%

EDUCATION
BA Design and Technology, Goldsmiths London (2022)

SKILLS
TypeScript, JavaScript, React, Next.js, Tailwind CSS, Storybook, Figma,
accessibility, web performance, HTML, CSS
"""


SAMPLE_JOBS = [
    # title, company, description
    (
        "Junior Backend Engineer",
        "Quickloop",
        "Looking for a junior Python developer to work on FastAPI services. "
        "Bachelor's degree, 1-3 years experience. Familiarity with PostgreSQL and Docker.",
    ),
    (
        "Senior Machine Learning Engineer",
        "Lyrebird",
        "Senior ML engineer to lead our LLM team. 7+ years of experience training "
        "and deploying PyTorch models, expertise in distributed training and CUDA.",
    ),
    (
        "Senior Frontend Engineer",
        "Lattice",
        "Build modern React applications with Next.js and TypeScript. 5+ years. "
        "Design system experience, Tailwind, accessibility a must.",
    ),
    (
        "iOS Engineer",
        "Bluewave",
        "Native iOS development with Swift and SwiftUI. UIKit experience required.",
    ),
    (
        "DevOps Engineer",
        "Ironforge",
        "Kubernetes, Terraform, CI/CD pipelines. Experience with AWS and GitOps required.",
    ),
]


@pytest.fixture
def isolated_db(tmp_path, monkeypatch):
    """Point jobhunt at a throw-away SQLite file just for this test."""
    db_file = tmp_path / "test.db"
    monkeypatch.setenv("JOBHUNT_DB_PATH", str(db_file))
    # Re-import so the engine picks up the new path.
    from importlib import reload
    import jobhunt.config as cfg
    import jobhunt.db as db
    reload(cfg)
    reload(db)
    # Reload anything that imports db at module level too.
    import jobhunt.cv as cv_mod
    reload(cv_mod)
    db.init_db()
    yield
    # Cleanup happens automatically via tmp_path.


def _seed_jobs(session, jobs):
    for title, company, desc in jobs:
        session.add(
            Job(
                fingerprint=f"fp-{title}-{company}".replace(" ", "-"),
                source="test",
                source_id=title,
                url=f"https://example.com/{title.replace(' ', '-')}",
                company=company,
                title=title,
                location="Remote",
                description=desc,
                description_hash="x",
            )
        )


def test_cosine_sanity():
    a = [1.0, 0.0, 0.0]
    b = [1.0, 0.0, 0.0]
    c = [0.0, 1.0, 0.0]
    assert cosine(a, b) == pytest.approx(1.0)
    assert cosine(a, c) == pytest.approx(0.0)


def test_parse_cv_txt_roundtrip():
    text = parse_cv("test.txt", JUNIOR_PY_CV.encode("utf-8"))
    assert "FastAPI" in text
    assert "PostgreSQL" in text


def test_parse_cv_rejects_unknown_ext():
    with pytest.raises(ValueError):
        parse_cv("evil.exe", b"some bytes")


def test_embed_returns_floats():
    vec, model = embed_text("python developer")
    assert isinstance(vec, list) and len(vec) >= 100
    assert all(isinstance(v, float) for v in vec)
    assert "MiniLM" in model or "minilm" in model.lower()


def test_pipeline_python_cv_matches_python_job(isolated_db):
    from jobhunt.cv import upload_cv as fresh_upload_cv, match_all_jobs as fresh_match
    from jobhunt.db import db_session as fresh_session

    with fresh_session() as s:
        _seed_jobs(s, SAMPLE_JOBS)

    info = fresh_upload_cv("alex.txt", JUNIOR_PY_CV.encode("utf-8"))
    assert "python" in info["languages"]
    assert "fastapi" in info["skills"]
    assert info["embedding_dim"] > 100

    fresh_match()

    with fresh_session() as s:
        ranked = (
            s.query(Job)
            .filter(Job.cv_match.is_not(None))
            .order_by(Job.cv_match.desc())
            .all()
        )
    assert ranked, "no jobs got a cv_match score"
    top_title = ranked[0].title.lower()
    # Top match for a junior Python CV should be the Python job.
    assert "backend" in top_title or "python" in top_title, (
        f"Expected a backend/python job at top; got {ranked[0].title}"
    )


def test_pipeline_ml_cv_matches_ml_job(isolated_db):
    from jobhunt.cv import upload_cv as fresh_upload_cv, match_all_jobs as fresh_match
    from jobhunt.db import db_session as fresh_session

    with fresh_session() as s:
        _seed_jobs(s, SAMPLE_JOBS)

    info = fresh_upload_cv("priya.txt", SENIOR_ML_CV.encode("utf-8"))
    assert "ml" in info["skills"]

    fresh_match()

    with fresh_session() as s:
        ranked = (
            s.query(Job)
            .filter(Job.cv_match.is_not(None))
            .order_by(Job.cv_match.desc())
            .all()
        )
    top = ranked[0]
    assert "machine learning" in top.title.lower() or "ml" in top.title.lower(), (
        f"Expected an ML job at top; got {top.title}"
    )


def test_pipeline_frontend_cv_matches_frontend_job(isolated_db):
    from jobhunt.cv import upload_cv as fresh_upload_cv, match_all_jobs as fresh_match
    from jobhunt.db import db_session as fresh_session

    with fresh_session() as s:
        _seed_jobs(s, SAMPLE_JOBS)

    info = fresh_upload_cv("jordan.txt", FRONTEND_REACT_CV.encode("utf-8"))
    assert "typescript" in info["languages"] or "javascript" in info["languages"]
    assert "react" in info["skills"]

    fresh_match()

    with fresh_session() as s:
        ranked = (
            s.query(Job)
            .filter(Job.cv_match.is_not(None))
            .order_by(Job.cv_match.desc())
            .all()
        )
    top = ranked[0]
    assert "frontend" in top.title.lower() or "react" in top.title.lower(), (
        f"Expected a frontend job at top; got {top.title}"
    )


def test_cv_status_lifecycle(isolated_db):
    from jobhunt.cv import upload_cv as fresh_upload_cv, cv_status as fresh_status, clear_cv as fresh_clear

    s0 = fresh_status()
    assert s0["loaded"] is False
    fresh_upload_cv("alex.txt", JUNIOR_PY_CV.encode("utf-8"))
    s1 = fresh_status()
    assert s1["loaded"] is True
    assert s1["filename"] == "alex.txt"
    fresh_clear()
    s2 = fresh_status()
    assert s2["loaded"] is False
