from jobhunt.dedup import fingerprint, normalize_company, normalize_location, normalize_title


def test_normalize_title_strips_seniority_and_parenthetical():
    assert normalize_title("Sr. Backend Engineer (Remote)") == "backend engineer"
    assert normalize_title("Senior Software Engineer - New Grad") == "software engineer"


def test_normalize_company_strips_suffixes():
    assert normalize_company("Acme Inc.") == "acme"
    assert normalize_company("Acme Corp") == "acme"


def test_fingerprint_collapses_seniority_variants():
    a = fingerprint("Acme Inc", "Senior Backend Engineer", "London")
    b = fingerprint("Acme Corp", "Backend Engineer (Hybrid)", "London")
    assert a == b


def test_fingerprint_distinguishes_real_role_diff():
    a = fingerprint("Acme", "Backend Engineer", "London")
    b = fingerprint("Acme", "Frontend Engineer", "London")
    assert a != b


def test_normalize_location_canonicalizes_pure_remote_synonyms():
    # The bug: one remote job arriving from N aggregators as "Remote" / "Worldwide" /
    # "Anywhere" / "100% Remote" split into N rows because these normalized differently.
    for variant in ("Remote", "Worldwide", "Anywhere", "100% Remote",
                    "Fully Remote", "Work From Home", "WFH", "Global"):
        assert normalize_location(variant) == "remote", variant


def test_normalize_location_keeps_region_qualified_remote_distinct():
    # "Remote, US" carries a geography — must NOT collapse into bare remote,
    # or a US-only remote merges with a global remote.
    assert normalize_location("Remote, US") != "remote"
    assert normalize_location("Cairo, Egypt") != "remote"
    # empty is left empty (not force-merged into remote)
    assert normalize_location("") == ""


def test_fingerprint_collapses_remote_synonyms():
    base = fingerprint("Acme", "Backend Engineer", "Remote")
    assert fingerprint("Acme", "Backend Engineer", "Worldwide") == base
    assert fingerprint("Acme", "Backend Engineer", "Anywhere") == base
    assert fingerprint("Acme", "Backend Engineer", "100% Remote") == base


def test_fingerprint_salt_distinguishes_distinct_openings():
    # Two genuinely different reqs at one company with identical company/title/location
    # must not collapse (which would overwrite the first opening's apply URL).
    base = fingerprint("Acme", "Backend Engineer", "Cairo")
    salted = fingerprint("Acme", "Backend Engineer", "Cairo", salt="req-2")
    assert base != salted
    # salt is stable and empty-salt is backwards compatible with the un-salted key
    assert fingerprint("Acme", "Backend Engineer", "Cairo", salt="req-2") == salted
    assert fingerprint("Acme", "Backend Engineer", "Cairo", salt="") == base


# ---------------------------------------------------------------------------
# Unicode safety (P3): Arabic titles must not normalize to "", NFC-equivalent
# strings must fingerprint identically.
# ---------------------------------------------------------------------------

import unicodedata


class TestUnicodeNormalization:
    def test_arabic_title_not_stripped_to_empty(self):
        assert normalize_title("محاسب أول") != ""

    def test_distinct_arabic_titles_get_distinct_fingerprints(self):
        fp1 = fingerprint("Acme Egypt", "محاسب", "Cairo, Egypt")
        fp2 = fingerprint("Acme Egypt", "مندوب مبيعات", "Cairo, Egypt")
        assert fp1 != fp2

    def test_nfc_equivalence(self):
        composed = "münchen"                                    # ü as one codepoint
        decomposed = unicodedata.normalize("NFD", "münchen")    # u + combining diaeresis
        assert fingerprint("Co", "Engineer", composed) == fingerprint("Co", "Engineer", decomposed)

    def test_umlaut_kept_distinct_from_bare_consonants(self):
        # Previously "münchen" was stripped to "mnchen" — indistinguishable from
        # a company literally named "mnchen".
        assert normalize_location("münchen") != normalize_location("mnchen")

    def test_ascii_normalization_unchanged(self):
        # Pure-ASCII normalization must be identical to the old behaviour.
        assert normalize_title("Sr. Backend Engineer (Remote)") == "backend engineer"
