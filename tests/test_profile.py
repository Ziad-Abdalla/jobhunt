"""P6: /profile page — loopback gate, save/load, secret-paste rejection."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from jobhunt.cowork_models import ApplicantProfile
from jobhunt.db import db_session, init_db
from jobhunt.main import app

# Browser form POSTs carry a same-origin Origin header; the app's CSRF
# middleware requires it on non-/api/ state changes.
_ORIGIN = {"origin": "http://testserver"}
local = TestClient(app, client=("127.0.0.1", 50000), headers=_ORIGIN)
remote = TestClient(app, client=("203.0.113.9", 50000), headers=_ORIGIN)


@pytest.fixture(autouse=True)
def _clean_profile():
    init_db()
    with db_session() as s:
        s.query(ApplicantProfile).delete()
    yield
    with db_session() as s:
        s.query(ApplicantProfile).delete()


class TestLoopbackGate:
    def test_remote_peer_403(self):
        r = remote.get("/profile")
        assert r.status_code == 403
        assert "loopback" in r.text.lower() or "local" in r.text.lower()

    def test_remote_post_403(self):
        r = remote.post("/profile", data={"full_name": "X"})
        assert r.status_code == 403

    def test_loopback_ok(self):
        assert local.get("/profile").status_code == 200


class TestSaveLoad:
    def test_save_then_render(self):
        r = local.post("/profile", data={
            "full_name": "Ziad Tester",
            "email": "z@example.com",
            "phone": "+20 100 000 0000",
            "location": "Cairo, Egypt",
            "linkedin_url": "https://linkedin.com/in/ziad",
            "github_url": "https://github.com/ziad",
            "portfolio_url": "",
            "work_authorization": "EG citizen",
            "salary_expectation": "negotiable",
            "cover_note": "Hello there.",
        }, follow_redirects=True)
        assert r.status_code == 200
        assert "Ziad Tester" in r.text
        with db_session() as s:
            p = s.get(ApplicantProfile, 1)
            assert p is not None
            assert p.email == "z@example.com"

    def test_lengths_capped(self):
        local.post("/profile", data={"full_name": "A" * 10_000})
        with db_session() as s:
            p = s.get(ApplicantProfile, 1)
            assert p is None or len(p.full_name) <= 256


class TestSecretPasteRejection:
    @pytest.mark.parametrize("bad", [
        "AKIAIOSFODNN7EXAMPLE",                      # AWS access key id
        "sk-abcdefghijklmnopqrstuvwx123456",         # sk- API key
        "ghp_" + "a" * 36,                           # GitHub PAT
        "-----BEGIN RSA PRIVATE KEY-----",           # PEM
        "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.x.y",  # JWT-ish
    ])
    def test_rejected(self, bad: str):
        r = local.post("/profile", data={"cover_note": bad})
        assert r.status_code == 400
        assert "secret" in r.text.lower() or "key" in r.text.lower()
        with db_session() as s:
            p = s.get(ApplicantProfile, 1)
            assert p is None or bad not in (p.cover_note or "")

    def test_normal_text_not_rejected(self):
        r = local.post("/profile", data={
            "cover_note": "I skey through problems and eyJoy debugging.",
        }, follow_redirects=True)
        assert r.status_code == 200
