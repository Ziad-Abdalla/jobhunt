"""P7: board-discovery generator — slug extraction + dedupe + review file."""

from __future__ import annotations

from jobhunt.board_discovery import (
    dedupe_against_existing,
    extract_board_slugs,
)

_FIXTURE = """
# Remote companies

- [Acme](https://boards.greenhouse.io/acme) — great place
- [Beta](https://job-boards.greenhouse.io/beta/jobs) — hiring
- [Gamma](https://jobs.lever.co/gamma) remote
- [Delta](https://jobs.ashbyhq.com/delta/careers)
- [Epsilon](https://epsilon.recruitee.com/) NL
- [Zeta](https://apply.workable.com/zeta/) EU
- [Paymob](https://jobs.smartrecruiters.com/Paymob) Egypt fintech
- [NoAts](https://acme.com/careers) — own site, not an ATS
- [Mail](mailto:jobs@x.com) — ignore
"""


class TestExtract:
    def test_extracts_known_ats_slugs(self):
        found = extract_board_slugs(_FIXTURE)
        pairs = {(f["source"], f["board"]) for f in found}
        assert ("greenhouse", "acme") in pairs
        assert ("greenhouse", "beta") in pairs
        assert ("lever", "gamma") in pairs
        assert ("ashby", "delta") in pairs
        assert ("recruitee", "epsilon") in pairs
        assert ("workable", "zeta") in pairs
        assert ("smartrecruiters", "Paymob") in pairs

    def test_ignores_non_ats_and_mailto(self):
        found = extract_board_slugs(_FIXTURE)
        boards = {f["board"] for f in found}
        assert "careers" not in boards
        assert not any(f["source"] == "company_site" for f in found)

    def test_no_duplicate_pairs(self):
        found = extract_board_slugs(_FIXTURE + _FIXTURE)  # same content twice
        pairs = [(f["source"], f["board"]) for f in found]
        assert len(pairs) == len(set(pairs))


class TestDirectories:
    def test_hiring_without_whiteboards_is_harvested(self):
        """TODO item 5 (2026-07-21): the hiring-without-whiteboards README
        is a curated company directory with many ATS links."""
        from jobhunt.board_discovery import DIRECTORY_URLS

        assert any("hiring-without-whiteboards" in u for u in DIRECTORY_URLS)


class TestDedupe:
    def test_drops_already_configured(self):
        found = extract_board_slugs(_FIXTURE)
        existing = [{"source": "greenhouse", "board": "acme"}]
        fresh = dedupe_against_existing(found, existing)
        pairs = {(f["source"], f["board"]) for f in fresh}
        assert ("greenhouse", "acme") not in pairs
        assert ("lever", "gamma") in pairs

    def test_case_insensitive_board_match(self):
        found = [{"source": "smartrecruiters", "board": "Paymob"}]
        existing = [{"source": "smartrecruiters", "board": "paymob"}]
        assert dedupe_against_existing(found, existing) == []


class TestCli:
    def test_discover_writes_review_file_not_sources_yaml(self, tmp_path, monkeypatch):
        import jobhunt.board_discovery as bd
        from jobhunt.cli import app as cli_app

        # No live fetch — stub the directory text.
        monkeypatch.setattr(bd, "fetch_directories", lambda *a, **k: _FIXTURE)
        out = tmp_path / "discovered.yaml"
        from typer.testing import CliRunner
        result = CliRunner().invoke(
            cli_app, ["discover-boards", "--output", str(out)]
        )
        assert result.exit_code == 0, result.output
        assert out.exists()
        body = out.read_text(encoding="utf-8")
        assert "greenhouse" in body
        assert "doctor" in body  # the verify-before-ship reminder header
        # sources.yaml must be untouched by discovery.
        from jobhunt.config import settings
        srcs = settings.sources_file.read_text(encoding="utf-8")
        assert "Delta" not in srcs and "gamma" not in srcs
