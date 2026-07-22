"""P6: /profile page — loopback gate, save/load, secret-paste rejection."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from jobhunt.cowork_models import ApplicantProfile
from jobhunt.db import db_session, init_db
from jobhunt.main import app

# base_url gives a loopback Host header (the anti-DNS-rebinding gate); the
# matching Origin satisfies the CSRF middleware on non-/api POSTs.
_ORIGIN = {"origin": "http://127.0.0.1"}
local = TestClient(app, base_url="http://127.0.0.1", client=("127.0.0.1", 50000), headers=_ORIGIN)
remote = TestClient(app, base_url="http://127.0.0.1", client=("203.0.113.9", 50000), headers=_ORIGIN)


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

    def test_dns_rebinding_host_rejected(self):
        # Loopback SOCKET peer but an attacker-controlled Host (the DNS
        # rebinding vector) must still be refused.
        rebind = TestClient(
            app, base_url="http://evil.example.com",
            client=("127.0.0.1", 50000), headers={"origin": "http://evil.example.com"},
        )
        assert rebind.get("/profile").status_code == 403

    def test_ipv4_mapped_loopback_allowed(self):
        # Dual-stack (HOST=::) reports IPv4 clients as ::ffff:127.0.0.1.
        mapped = TestClient(
            app, base_url="http://127.0.0.1",
            client=("::ffff:127.0.0.1", 50000), headers={"origin": "http://127.0.0.1"},
        )
        assert mapped.get("/profile").status_code == 200

    def test_spoofed_forwarded_for_ignored(self):
        # A remote peer can't fake loopback via X-Forwarded-For — the gate
        # reads the socket peer, not the header.
        r = remote.get("/profile", headers={"x-forwarded-for": "127.0.0.1"})
        assert r.status_code == 403


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


class TestFullAutoProfileFields:
    def test_new_fields_render(self):
        r = local.get("/profile")
        assert r.status_code == 200
        for name in ("cv_path_egypt", "cv_path_remote", "notice_period",
                     "earliest_start", "how_heard_default", "eeo_default"):
            assert f'name="{name}"' in r.text, name

    def test_new_fields_save_roundtrip(self):
        r = local.post("/profile", data={
            "full_name": "Z", "cv_path_egypt": r"C:\cv\eg.pdf",
            "cv_path_remote": r"C:\cv\remote.pdf",
            "notice_period": "1 month", "earliest_start": "immediately",
            "how_heard_default": "Job board", "eeo_default": "Prefer not to say",
        }, follow_redirects=False)
        assert r.status_code == 303
        r2 = local.get("/profile")
        assert r"C:\cv\eg.pdf" in r2.text
        assert "1 month" in r2.text


class TestAnswerBankUI:
    @pytest.fixture(autouse=True)
    def _clean_bank(self):
        from jobhunt.cowork_models import AnswerBank

        with db_session() as s:
            s.query(AnswerBank).delete()
        yield
        with db_session() as s:
            s.query(AnswerBank).delete()

    def _seed(self) -> int:
        from jobhunt.cowork_models import AnswerBank

        with db_session() as s:
            s.add(AnswerBank(question="Notice period?",
                             question_norm="notice period", answer="1 month"))
        with db_session() as s:
            return s.query(AnswerBank).one().id

    def test_bank_renders_on_profile(self):
        self._seed()
        r = local.get("/profile")
        assert "Notice period?" in r.text and "1 month" in r.text

    def test_bank_update(self):
        from jobhunt.cowork_models import AnswerBank

        bank_id = self._seed()
        r = local.post(f"/profile/answers/{bank_id}", data={"answer": "2 weeks"},
                       follow_redirects=False)
        assert r.status_code == 303
        with db_session() as s:
            assert s.get(AnswerBank, bank_id).answer == "2 weeks"

    def test_bank_delete(self):
        from jobhunt.cowork_models import AnswerBank

        bank_id = self._seed()
        local.post(f"/profile/answers/{bank_id}/delete", follow_redirects=False)
        with db_session() as s:
            assert s.get(AnswerBank, bank_id) is None

    def test_bank_update_rejects_secrets(self):
        bank_id = self._seed()
        r = local.post(f"/profile/answers/{bank_id}",
                       data={"answer": "ghp_" + "a" * 36}, follow_redirects=False)
        assert r.status_code == 400

    def test_bank_routes_loopback_gated(self):
        bank_id = self._seed()
        assert remote.post(f"/profile/answers/{bank_id}",
                           data={"answer": "x"}).status_code == 403
        assert remote.post(f"/profile/answers/{bank_id}/delete").status_code == 403
