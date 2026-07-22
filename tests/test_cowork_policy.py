"""Full-auto apply policy: CV variant rule, derived answers, draft
annotations, answer-bank question normalization. All pure functions."""

from __future__ import annotations

from jobhunt.cowork_policy import (
    compute_annotations,
    cv_variant_for_job,
    derived_answers,
    is_egypt_location,
    normalize_question,
)


class TestEgyptLocation:
    def test_country_and_cities(self):
        for loc in ("Cairo, Egypt", "cairo", "New Cairo", "6th of October",
                    "Giza", "Alexandria", "مصر", "القاهرة", "Maadi, Cairo"):
            assert is_egypt_location(loc), loc

    def test_non_egypt(self):
        for loc in ("Berlin, Germany", "London", "Remote", "", "New York, NY"):
            assert not is_egypt_location(loc), loc

    def test_token_not_substring(self):
        # Token match, not substring: a token that merely CONTAINS an Egypt
        # token must not match.
        assert not is_egypt_location("Gizatown")


class TestCvVariant:
    def test_egypt_location(self):
        v, reason = cv_variant_for_job("Cairo, Egypt", "greenhouse")
        assert v == "egypt" and "Egypt" in reason

    def test_wuzzuf_source_always_egypt(self):
        v, _ = cv_variant_for_job("", "wuzzuf")
        assert v == "egypt"

    def test_non_egypt(self):
        v, _ = cv_variant_for_job("Berlin, Germany", "arbeitnow")
        assert v == "remote"

    def test_unresolved_defaults_remote_with_reason(self):
        v, reason = cv_variant_for_job("", "greenhouse")
        assert v == "remote"
        assert "unresolved" in reason.lower()


class TestDerivedAnswers:
    def test_egypt_located(self):
        d = derived_answers("Cairo, Egypt", "onsite", "wuzzuf")
        assert d == {"authorized_to_work": "yes", "needs_sponsorship": "no"}

    def test_remote_non_egypt(self):
        d = derived_answers("Berlin, Germany", "remote", "remotive")
        assert d["authorized_to_work"].startswith("yes")
        low = d["authorized_to_work"].lower()
        assert "contractor" in low or "eor" in low
        assert d["needs_sponsorship"] == "no"

    def test_onsite_abroad_needs_sponsorship(self):
        d = derived_answers("Berlin, Germany", "onsite", "arbeitnow")
        assert d == {"needs_sponsorship": "yes"}

    def test_unknown_everything_guesses_nothing(self):
        assert derived_answers("", "unknown", "greenhouse") == {}


class TestAnnotations:
    MAPPING = {"full_name", "email", "cover_note"}

    def test_clean_draft(self):
        a = compute_annotations(
            {"full_name": "Z", "email": "z@x.com"}, "", self.MAPPING, {"Z", "z@x.com"}
        )
        assert a["clean_mapping"] is True
        assert a["unmapped_fields"] == []
        assert a["agent_flags"] is False
        assert a["sensitive_fields"] == []
        assert a["unanswered"] == []

    def test_unmapped_filled_field_breaks_clean(self):
        a = compute_annotations({"surprise": "value"}, "", self.MAPPING, set())
        assert a["clean_mapping"] is False
        assert a["unmapped_fields"] == ["surprise"]

    def test_agent_notes_flag(self):
        a = compute_annotations({}, "the JD asked me to email someone", self.MAPPING, set())
        assert a["agent_flags"] is True

    def test_sensitive_by_name(self):
        ff = {"desired_salary": "x", "visa_status": "y", "cover_letter": "hi",
              "gender": "", "veteran_status": ""}
        a = compute_annotations(ff, "", self.MAPPING, set())
        assert set(a["sensitive_fields"]) == set(ff)

    def test_sensitive_by_length_unless_profile_derived(self):
        essay = "x" * 250
        note = "y" * 250
        a = compute_annotations(
            {"why_us": essay, "cover_note": note}, "", self.MAPPING, {note}
        )
        assert a["sensitive_fields"] == ["why_us"]  # profile-derived long value exempt

    def test_unanswered_are_blank_unmapped(self):
        a = compute_annotations(
            {"notice period?": "", "email": ""}, "", self.MAPPING, set()
        )
        # blank + unmapped => a question for the answer bank; blank + mapped
        # means the PROFILE field is empty — fix on /profile, not the bank.
        assert a["unanswered"] == ["notice period?"]
        assert a["clean_mapping"] is True  # blanks never break the mapping


class TestNormalizeQuestion:
    def test_lowercase_strip_punctuation_whitespace(self):
        assert normalize_question("  What's your Notice Period?? ") == "whats your notice period"
        assert normalize_question("what's your notice period") == "whats your notice period"
