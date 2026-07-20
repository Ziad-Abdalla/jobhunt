"""P4: home-region mapping + reachability weight table (pure functions)."""

from __future__ import annotations

from jobhunt.scoring import (
    GEO_BUCKETS,
    UNREACHABLE_WEIGHT,
    home_region_from_location,
    reachability_weights,
)


def test_home_region_examples() -> None:
    # The settings docstring's own examples must all resolve.
    assert home_region_from_location("Cairo, Egypt") == "other"
    assert home_region_from_location("Berlin, Germany") == "eu"
    assert home_region_from_location("London, UK") == "uk"
    assert home_region_from_location("Sydney, Australia") == "other"
    assert home_region_from_location("New York, USA") == "us"
    assert home_region_from_location("Austin, United States") == "us"
    assert home_region_from_location("united kingdom") == "uk"


def test_home_region_unknown_and_edge() -> None:
    assert home_region_from_location("") == ""
    assert home_region_from_location("   ") == ""
    # Unrecognized text must be '' (never penalize on a guess), NOT 'other' —
    # otherwise "New York, NY" would demote a US user's reachable us-only jobs.
    assert home_region_from_location("Atlantis") == ""


def test_home_region_city_state_forms_never_penalize() -> None:
    # The most common US location format carries no country token; it must
    # resolve to '' (no penalty), not 'other' (review finding, 2026-07-20).
    for loc in ("New York, NY", "San Francisco, CA", "Austin, TX",
                "Seattle, Washington", "Los Angeles"):
        assert home_region_from_location(loc) == "", loc


def test_home_region_native_language_names() -> None:
    # Native spellings must not fall through to '' (review finding).
    assert home_region_from_location("München, Deutschland") == "eu"
    assert home_region_from_location("Wien, Österreich") == "eu"
    assert home_region_from_location("Madrid, España") == "eu"
    assert home_region_from_location("Warszawa, Polska") == "eu"


def test_home_region_eea_counts_as_eu() -> None:
    # "EU only" postings routinely mean EU/EEA.
    assert home_region_from_location("Oslo, Norway") == "eu"


def test_home_region_recognized_other_countries() -> None:
    assert home_region_from_location("Toronto, Canada") == "other"
    assert home_region_from_location("Dubai, United Arab Emirates") == "other"
    assert home_region_from_location("القاهرة، مصر") == "other"
    # "Georgia" is deliberately unmapped (US state / country homograph).
    assert home_region_from_location("Tbilisi, Georgia") == ""


def test_northern_ireland_is_uk_dublin_is_eu() -> None:
    assert home_region_from_location("Belfast, Northern Ireland") == "uk"
    assert home_region_from_location("Dublin, Ireland") == "eu"


def test_weights_unknown_home_never_penalizes() -> None:
    w = reachability_weights("")
    assert set(w) == set(GEO_BUCKETS)
    assert all(v == 1.0 for v in w.values())


def test_weights_egypt_user_penalizes_all_three_only_buckets() -> None:
    w = reachability_weights("other")
    assert w["us-only"] == UNREACHABLE_WEIGHT
    assert w["uk-only"] == UNREACHABLE_WEIGHT
    assert w["eu-only"] == UNREACHABLE_WEIGHT
    # Conservative buckets are never punished.
    assert w["restricted-other"] == 1.0
    assert w["unrestricted"] == 1.0
    assert w["unknown"] == 1.0


def test_weights_us_user() -> None:
    w = reachability_weights("us")
    assert w["us-only"] == 1.0
    assert w["uk-only"] == UNREACHABLE_WEIGHT
    assert w["eu-only"] == UNREACHABLE_WEIGHT


def test_weights_uk_is_not_eu() -> None:
    w = reachability_weights("uk")
    assert w["uk-only"] == 1.0
    assert w["eu-only"] == UNREACHABLE_WEIGHT
    w = reachability_weights("eu")
    assert w["eu-only"] == 1.0
    assert w["uk-only"] == UNREACHABLE_WEIGHT
