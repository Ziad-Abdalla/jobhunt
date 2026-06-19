"""Regression tests for the 2026-06-19 multi-agent bug sweep."""

from __future__ import annotations

import tomllib
from pathlib import Path

import jobhunt
from jobhunt.dedup import fingerprint
from jobhunt.extract import extract


def _level(title: str, desc: str = "") -> str:
    return extract(desc, title=title).level


# --- version drift (P0): __version__ must match pyproject ---
def test_version_matches_pyproject():
    pyproject = Path(jobhunt.__file__).resolve().parents[2] / "pyproject.toml"
    data = tomllib.loads(pyproject.read_text())
    assert jobhunt.__version__ == data["project"]["version"]


# --- staff/lead mislabel: local roles must NOT be tagged senior ---
def test_local_staff_and_lead_titles_are_not_senior():
    for t in ["Bar Staff", "Kitchen Staff", "Waiting Staff", "Care Staff",
              "Sales Lead", "Lead Generator"]:
        lvl = _level(t)
        assert lvl not in ("staff", "lead"), f"{t!r} mislabeled as {lvl!r}"


def test_tech_staff_and_lead_titles_are_still_senior():
    assert _level("Staff Software Engineer") == "staff"
    assert _level("Lead Developer") == "lead"
    assert _level("Engineering Lead") == "lead"


# --- dedup: distinct senior tiers must NOT collapse into one fingerprint ---
def test_distinct_seniority_tiers_have_distinct_fingerprints():
    fps = {
        fingerprint("Acme", "Staff Engineer", "London"),
        fingerprint("Acme", "Lead Engineer", "London"),
        fingerprint("Acme", "Principal Engineer", "London"),
        fingerprint("Acme", "Engineer", "London"),
    }
    # Four genuinely different roles -> four different fingerprints.
    assert len(fps) == 4


def test_dedup_still_ignores_pure_formatting_noise():
    # Sr./Junior and parentheticals are still treated as the same role.
    a = fingerprint("Acme", "Sr. Backend Engineer (Remote)", "London")
    b = fingerprint("Acme", "Backend Engineer", "London")
    assert a == b


def test_location_country_suffix_variants_dont_double_count():
    # The same job aggregated from several sources with different location
    # strings must collapse to one fingerprint, not inflate the count.
    base = fingerprint("Acme", "Engineer", "London")
    assert fingerprint("Acme", "Engineer", "London, UK") == base
    assert fingerprint("Acme", "Engineer", "London, United Kingdom") == base
    assert fingerprint("Acme", "Engineer", "London, England") == base
