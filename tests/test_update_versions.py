"""Update checking must compare versions numerically (not as strings) and pick
the newest GitHub tag — the install ships from a git tag, not PyPI."""

from jobhunt.main import _parse_version, _pick_latest_tag


def test_parse_version_strips_v_and_splits():
    assert _parse_version("v0.13.1") == (0, 13, 1)
    assert _parse_version("0.9.2") == (0, 9, 2)


def test_parse_version_is_resilient_to_junk():
    assert _parse_version("nightly") == (0,)
    assert _parse_version("") == (0,)


def test_pick_latest_tag_uses_numeric_order_not_string_order():
    # The string-sort trap: "v0.9.2" > "v0.13.1" alphabetically, but 0.13.1 is newer.
    tags = ["v0.7.3", "v0.9.2", "v0.11.2", "v0.13.0", "v0.13.1"]
    assert _pick_latest_tag(tags) == "v0.13.1"


def test_pick_latest_tag_ignores_non_version_tags():
    assert _pick_latest_tag(["latest", "v1.2.0", "stable"]) == "v1.2.0"


def test_pick_latest_tag_empty_returns_blank():
    assert _pick_latest_tag([]) == ""
