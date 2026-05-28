"""Tests for the per-platform bounty parsers."""

from __future__ import annotations

from jobhunt.bounties import (
    _parse_bugcrowd,
    _parse_hackerone,
    _parse_intigriti,
    _parse_yeswehack,
)


def test_hackerone_parse_cash_program() -> None:
    entry = {
        "name": "Example",
        "url": "https://hackerone.com/example",
        "handle": "example",
        "offers_bounties": True,
        "offers_swag": False,
        "submission_state": "open",
        "response_efficiency_percentage": 95,
        "average_time_to_report_resolved": 12,
        "targets": {"in_scope": [{"asset_identifier": "api.example.com"}]},
    }
    p = _parse_hackerone(entry)
    assert p is not None
    assert p.platform == "hackerone"
    assert p.pays == "cash"
    assert p.state == "open"
    assert p.response_efficiency_pct == 95
    assert p.avg_days_to_resolve == 12
    assert "api.example.com" in p.domains
    # H1 doesn't expose min/max in this dataset.
    assert p.min_bounty is None
    assert p.max_bounty is None


def test_hackerone_swag_only() -> None:
    p = _parse_hackerone({
        "name": "Swaggy",
        "url": "https://hackerone.com/swaggy",
        "offers_bounties": False,
        "offers_swag": True,
    })
    assert p is not None
    assert p.pays == "swag"


def test_bugcrowd_parse_with_max_payout() -> None:
    entry = {
        "name": "Acme",
        "url": "https://bugcrowd.com/acme",
        "max_payout": 7500,
        "targets": {"in_scope": [{"asset_identifier": "acme.com"}]},
    }
    p = _parse_bugcrowd(entry)
    assert p is not None
    assert p.platform == "bugcrowd"
    assert p.max_bounty == 7500
    assert p.currency == "USD"
    assert p.pays == "cash"


def test_intigriti_structured_currency() -> None:
    entry = {
        "name": "EuroCorp",
        "url": "https://intigriti.com/programs/euro",
        "status": "open",
        "min_bounty": {"value": 50, "currency": "EUR"},
        "max_bounty": {"value": 2500, "currency": "EUR"},
    }
    p = _parse_intigriti(entry)
    assert p is not None
    assert p.platform == "intigriti"
    assert p.min_bounty == 50
    assert p.max_bounty == 2500
    assert p.currency == "EUR"
    assert p.pays == "cash"
    assert p.state == "open"


def test_yeswehack_flat_ints() -> None:
    entry = {
        "id": "outscale",
        "name": "OUTSCALE",
        "min_bounty": 50,
        "max_bounty": 5000,
        "disabled": False,
    }
    p = _parse_yeswehack(entry)
    assert p is not None
    assert p.min_bounty == 50
    assert p.max_bounty == 5000
    assert p.currency == "EUR"
    assert p.state == "open"


def test_skips_entry_without_name() -> None:
    assert _parse_hackerone({"url": "x"}) is None
    assert _parse_bugcrowd({}) is None
    assert _parse_intigriti({}) is None
    assert _parse_yeswehack({}) is None
