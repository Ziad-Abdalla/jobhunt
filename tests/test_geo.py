"""Geo-eligibility extraction (P3) — 'Remote (US only)' must not look
apply-able from Egypt."""

from __future__ import annotations

import pytest

from jobhunt.extract import extract_geo


@pytest.mark.parametrize("text,expected", [
    # us-only
    ("This role is US only.", "us-only"),
    ("Open to candidates located in the United States only", "us-only"),
    ("You must be authorized to work in the United States", "us-only"),
    ("Must have US work authorization", "us-only"),
    ("Applicants must be based in the US.", "us-only"),
    # uk-only
    ("You must have the right to work in the UK", "uk-only"),
    ("UK only — no visa sponsorship", "uk-only"),
    # eu-only
    ("Candidates must be based in the EU", "eu-only"),
    ("EU/EEA work permit required", "eu-only"),
    ("This position is open to Europe only", "eu-only"),
    # restricted-other
    ("Must be located in Canada", "restricted-other"),
    ("Requires 4 hours timezone overlap with PST", "restricted-other"),
    ("Working hours within CET +/- 2 hours", "restricted-other"),
    # unrestricted
    ("Work from anywhere in the world", "unrestricted"),
    ("Fully remote, no location restrictions", "unrestricted"),
    ("We hire globally distributed teammates", "unrestricted"),
    ("Open to candidates worldwide", "unrestricted"),
    # unknown
    ("We are a fast-growing startup looking for a backend engineer.", "unknown"),
    ("", "unknown"),
])
def test_buckets(text, expected):
    assert extract_geo(text) == expected


def test_specific_region_beats_unrestricted():
    text = "Work from anywhere in the world — as long as you are US based candidates only."
    assert extract_geo(text) == "us-only"


def test_title_is_searched_too():
    assert extract_geo("", title="Backend Engineer (Remote, US only)") == "us-only"
