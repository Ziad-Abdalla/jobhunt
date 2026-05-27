"""Tests for improved remote detection (strong vs weak patterns)."""

from jobhunt.extract import extract


def test_remote_strong_patterns():
    e = extract("Fully remote position with competitive salary.", title="Engineer")
    assert e.remote == "remote"

    e = extract("This is a 100% remote role.", title="Engineer")
    assert e.remote == "remote"

    e = extract("Remote-first company.", title="Engineer")
    assert e.remote == "remote"

    e = extract("Work from home available.", title="Engineer")
    assert e.remote == "remote"


def test_remote_in_title():
    e = extract("Build great things.", title="Remote Software Engineer")
    assert e.remote == "remote"


def test_remote_in_description_opening():
    e = extract("Remote — We are looking for an engineer.", title="Engineer")
    assert e.remote == "remote"


def test_hybrid_detected():
    e = extract("This is a hybrid role, 3 days in office.", title="Engineer")
    assert e.remote == "hybrid"


def test_onsite_detected():
    e = extract("This is an on-site role in our NYC office.", title="Engineer")
    assert e.remote == "onsite"


def test_unknown_when_no_signal():
    e = extract("Build widgets with our team.", title="Widget Builder")
    assert e.remote == "unknown"


def test_remote_deep_in_description_not_matched():
    long_text = "x " * 200 + "remote debugging tools are essential" + " x" * 100
    e = extract(long_text, title="Engineer")
    assert e.remote == "unknown"


def test_german_internship_detected():
    e = extract("Praktikum in unserem Berliner Büro.", title="Praktikant Software")
    assert e.level == "intern"

    e = extract("", title="Werkstudent Frontend Development")
    assert e.level == "intern"
