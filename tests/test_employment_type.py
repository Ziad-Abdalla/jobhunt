"""Tests for employment type normalization and new extraction patterns."""

from jobhunt.refresh import _normalize_employment_type


class TestEmploymentTypeNormalization:
    def test_fulltime_variants(self):
        assert _normalize_employment_type("FullTime") == "Full-time"
        assert _normalize_employment_type("Full Time") == "Full-time"
        assert _normalize_employment_type("Full-time") == "Full-time"
        assert _normalize_employment_type("full-time") == "Full-time"
        assert _normalize_employment_type("Permanent") == "Full-time"
        assert _normalize_employment_type("Full-time permanent") == "Full-time"

    def test_parttime_variants(self):
        assert _normalize_employment_type("Part-time") == "Part-time"
        assert _normalize_employment_type("Part Time") == "Part-time"
        assert _normalize_employment_type("Side") == "Part-time"

    def test_contract_variants(self):
        assert _normalize_employment_type("Contract") == "Contract"
        assert _normalize_employment_type("Contractor") == "Contract"
        assert _normalize_employment_type("Freelance") == "Contract"
        assert _normalize_employment_type("Temporary") == "Contract"

    def test_wuzzuf_student_bucket(self):
        # Live straggler found 2026-07-21 (1 row): Wuzzuf's zero-experience
        # student bucket must fold into the 4 canonical types.
        assert _normalize_employment_type("No Experience Required / Student") == "Internship"

    def test_jsearch_v2_contractor_variants(self):
        # Observed live 2026-07-21: JSearch /search-v2 emits "Full Time
        # Contractor" (and dash variants) — must fold into the 4 canonical types.
        assert _normalize_employment_type("Full Time Contractor") == "Contract"
        assert _normalize_employment_type("Full-time Contractor") == "Contract"
        assert _normalize_employment_type("Part Time Contractor") == "Contract"

    def test_internship_variants(self):
        assert _normalize_employment_type("Internship") == "Internship"
        assert _normalize_employment_type("Intern") == "Internship"
        assert _normalize_employment_type("Working student") == "Internship"
        assert _normalize_employment_type("Apprenticeship") == "Internship"

    def test_german_labels(self):
        assert _normalize_employment_type("berufserfahren") == "Full-time"
        assert _normalize_employment_type("berufseinstieg") == "Full-time"
        assert _normalize_employment_type("teamleitung") == "Full-time"
        assert _normalize_employment_type("hilfstätigkeit / student") == "Internship"

    def test_unknown_passthrough(self):
        assert _normalize_employment_type("") == "unknown"
        assert _normalize_employment_type("unknown") == "unknown"

    def test_unrecognized_passthrough(self):
        assert _normalize_employment_type("SomethingNew") == "SomethingNew"

    def test_case_insensitive(self):
        assert _normalize_employment_type("FULLTIME") == "Full-time"
        assert _normalize_employment_type("CONTRACT") == "Contract"
