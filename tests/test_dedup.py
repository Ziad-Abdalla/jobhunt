from jobhunt.dedup import fingerprint, normalize_company, normalize_title


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
