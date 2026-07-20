"""P9+P10: /apply/tailor route + Cowork export tailoring block + CLI."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from jobhunt.cowork_models import Application
from jobhunt.db import db_session, init_db
from jobhunt.main import app
from jobhunt.models import CVProfile, Job

_TEST_COMPANY = "TailorRouteAcme"
client = TestClient(app, base_url="http://127.0.0.1", client=("127.0.0.1", 50000),
                    headers={"origin": "http://127.0.0.1"})


def _job_id() -> int:
    with db_session() as s:
        return s.query(Job).filter(Job.company == _TEST_COMPANY).one().id


@pytest.fixture(autouse=True)
def _seed():
    init_db()
    def _clean():
        with db_session() as s:
            ids = [j.id for j in s.query(Job).filter(Job.company == _TEST_COMPANY)]
            if ids:
                s.query(Application).filter(Application.job_id.in_(ids)).delete()
            s.query(Job).filter(Job.company == _TEST_COMPANY).delete()
            s.query(CVProfile).delete()
    _clean()
    with db_session() as s:
        s.add(Job(
            fingerprint="tailor-" + "1" * 25, source="t", source_id="1",
            url="https://boards.greenhouse.io/acme/1", company=_TEST_COMPANY,
            title="Django Backend Engineer Zx", location="Cairo, Egypt",
            description="We need Python, Django, Docker, PostgreSQL, Redis.",
            skills=["docker", "postgres", "redis"], languages=["python"],
            apply_kind="ats", apply_domain="boards.greenhouse.io", score=1.0,
        ))
    yield
    _clean()


def _load_cv():
    with db_session() as s:
        s.add(CVProfile(
            id=1, filename="cv.txt",
            text=("Jane Doe\njane@example.com | +20 100 123 4567\n\n"
                  "EXPERIENCE\nBackend engineer, built Django + Docker services.\n"
                  "EDUCATION\nBSc CS.\nSKILLS\nPython, Django, Docker.\n" + "word " * 200),
            detected_skills=["docker", "django"], detected_languages=["python"],
        ))


class TestTailorRoute:
    def test_no_cv_prompts_upload(self):
        r = client.get(f"/apply/tailor/{_job_id()}")
        assert r.status_code == 200
        assert "/cv" in r.text

    def test_report_renders_with_cv(self):
        _load_cv()
        r = client.get(f"/apply/tailor/{_job_id()}")
        assert r.status_code == 200
        assert "Django Backend Engineer Zx" in r.text
        assert "redis" in r.text  # a missing keyword surfaced
        assert "coverage" in r.text.lower()

    def test_markdown_download(self):
        _load_cv()
        r = client.get(f"/apply/tailor/{_job_id()}.md")
        assert r.status_code == 200
        assert "text/markdown" in r.headers["content-type"]
        assert "# Tailoring sheet" in r.text

    def test_unknown_job_404(self):
        assert client.get("/apply/tailor/99999999").status_code == 404
        assert client.get("/apply/tailor/99999999.md").status_code == 404

    def test_loopback_gated(self):
        # Applicant data (CV skills, name in the .md) — remote peers refused,
        # like /profile and the queue view.
        remote = TestClient(app, base_url="http://127.0.0.1",
                            client=("203.0.113.9", 50000))
        _load_cv()
        assert remote.get(f"/apply/tailor/{_job_id()}").status_code == 403
        assert remote.get(f"/apply/tailor/{_job_id()}.md").status_code == 403


class TestExportTailoring:
    def test_export_carries_tailoring_block(self, monkeypatch):
        from jobhunt.config import settings
        monkeypatch.setattr(settings, "cowork_export", True)
        _load_cv()
        with db_session() as s:
            s.add(Application(job_id=_job_id(), status="queued"))
        data = client.get("/api/cowork/export", params={"status": "queued"}).json()
        rec = next(a for a in data["applications"]
                   if a["job"]["company"] == _TEST_COMPANY)
        t = rec["tailoring"]
        assert "coverage_pct" in t
        assert "python" in t["matched"]
        assert "redis" in t["missing"]
        # Only derived lists cross — not the raw CV (that's already in cv_text).
        assert "suggested_skills_line" in t


class TestCli:
    def test_cli_tailor_prints_markdown(self):
        _load_cv()
        from typer.testing import CliRunner

        from jobhunt.cli import app as cli_app
        result = CliRunner().invoke(cli_app, ["tailor", str(_job_id())])
        assert result.exit_code == 0, result.output
        assert "# Tailoring sheet" in result.output
