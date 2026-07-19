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
