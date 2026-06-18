"""Level defaulting must not mislabel zero-experience local roles as 'mid',
or the entry-level / 0-experience filter silently drops them."""

from jobhunt.refresh import _resolve_level


def test_detected_level_is_always_kept():
    assert _resolve_level("senior", "nontech", has_description=True) == "senior"
    assert _resolve_level("intern", "tech", has_description=True) == "intern"


def test_unqualified_tech_role_defaults_to_mid():
    # Industry convention: a bare "Software Engineer" is mid-level.
    assert _resolve_level("unknown", "tech", has_description=True) == "mid"


def test_unqualified_local_role_defaults_to_entry_not_mid():
    # A "Cleaner" or "Catering Assistant" with no seniority word is entry-level
    # work — it must be reachable by the 0-experience filter.
    assert _resolve_level("unknown", "nontech", has_description=True) == "entry"
    assert _resolve_level("unknown", "other", has_description=True) == "entry"


def test_thin_description_stays_unknown():
    assert _resolve_level("unknown", "tech", has_description=False) == "unknown"
    assert _resolve_level("unknown", "nontech", has_description=False) == "unknown"
