"""P5: pure apply-URL classifier tests."""

from __future__ import annotations

import pytest

from jobhunt.apply_target import classify_apply

# ── ATS hosts ──────────────────────────────────────────────────────────────

@pytest.mark.parametrize(
    "url,domain",
    [
        ("https://boards.greenhouse.io/stripe/jobs/123", "boards.greenhouse.io"),
        ("https://job-boards.greenhouse.io/datadog/jobs/1", "job-boards.greenhouse.io"),
        ("https://job-boards.eu.greenhouse.io/acme/jobs/1", "job-boards.eu.greenhouse.io"),
        ("https://jobs.lever.co/netflix/uuid", "jobs.lever.co"),
        ("https://jobs.eu.lever.co/acme/uuid", "jobs.eu.lever.co"),
        ("https://jobs.ashbyhq.com/linear/uuid", "jobs.ashbyhq.com"),
        ("https://apply.workable.com/acme/j/ABC/", "apply.workable.com"),
        ("https://jobs.smartrecruiters.com/Acme/123", "jobs.smartrecruiters.com"),
        ("https://acme.recruitee.com/o/dev", "acme.recruitee.com"),
        ("https://acme.wd5.myworkdayjobs.com/en-US/ext/job/X", "acme.wd5.myworkdayjobs.com"),
        ("https://acme.bamboohr.com/careers/42", "acme.bamboohr.com"),
        ("https://jobs.jobvite.com/acme/job/x", "jobs.jobvite.com"),
        ("https://careers-acme.icims.com/jobs/123/login", "careers-acme.icims.com"),
        ("https://acme.breezy.hr/p/dev", "acme.breezy.hr"),
        ("https://acme.applytojob.com/apply/x", "acme.applytojob.com"),
        ("https://acme.teamtailor.com/jobs/123", "acme.teamtailor.com"),
        ("https://acme.jobs.personio.de/job/1", "acme.jobs.personio.de"),
        ("https://join.com/companies/acme/123", "join.com"),
        ("https://acme.taleo.net/careersection/x", "acme.taleo.net"),
        ("https://career5.successfactors.com/career?x=1", "career5.successfactors.com"),
    ],
)
def test_ats_hosts(url: str, domain: str) -> None:
    kind, dom = classify_apply(url)
    assert kind == "ats"
    assert dom == domain


# ── Aggregator relays (every board jobhunt scrapes + big generic boards) ───

@pytest.mark.parametrize(
    "url,domain",
    [
        ("https://wuzzuf.net/jobs/p/12345-accountant", "wuzzuf.net"),
        ("https://remotive.com/remote-jobs/software-dev/x-123", "remotive.com"),
        ("https://www.workingnomads.com/jobs?job=x", "workingnomads.com"),
        ("https://weworkremotely.com/remote-jobs/x", "weworkremotely.com"),
        ("https://www.python.org/jobs/123/", "python.org"),
        ("https://www.arbeitnow.com/jobs/companies/x/y", "arbeitnow.com"),
        ("https://www.arbeitsagentur.de/jobsuche/jobdetail/123", "arbeitsagentur.de"),
        ("https://himalayas.app/jobs/123", "himalayas.app"),
        ("https://jobicy.com/jobs/123", "jobicy.com"),
        ("https://remoteok.com/remote-jobs/123", "remoteok.com"),
        ("https://www.themuse.com/jobs/acme/dev", "themuse.com"),
        ("https://news.ycombinator.com/item?id=1#2", "news.ycombinator.com"),
        ("https://www.reed.co.uk/jobs/cleaner/123", "reed.co.uk"),
        ("https://jooble.org/desc/123", "jooble.org"),
        ("https://www.indeed.com/viewjob?jk=1", "indeed.com"),
        ("https://www.linkedin.com/jobs/view/1", "linkedin.com"),
        ("https://www.glassdoor.com/job-listing/1", "glassdoor.com"),
        ("https://www.ziprecruiter.com/c/x/job/1", "ziprecruiter.com"),
        ("https://www.stepstone.de/stellenangebote--x", "stepstone.de"),
        ("https://www.xing.com/jobs/1", "xing.com"),
        ("https://www.totaljobs.com/job/1", "totaljobs.com"),
        ("https://www.cv-library.co.uk/job/1", "cv-library.co.uk"),
        ("https://www.talent.com/view?id=1", "talent.com"),
        ("https://www.monster.com/job-openings/x", "monster.com"),
    ],
)
def test_aggregator_hosts(url: str, domain: str) -> None:
    kind, dom = classify_apply(url)
    assert kind == "aggregator_relay"
    assert dom == domain


# ── Company sites (the fallback) ───────────────────────────────────────────

@pytest.mark.parametrize(
    "url,domain",
    [
        ("https://stripe.com/jobs/listing/x", "stripe.com"),
        ("https://careers.datadoghq.com/detail/123/", "careers.datadoghq.com"),
        ("https://www.databricks.com/company/careers/x", "databricks.com"),
        ("https://lifeattiktok.com/search/123", "lifeattiktok.com"),
        # Niche job boards we don't know land here too — conservative routing.
        ("https://www.persy.jobs/jobs/1", "persy.jobs"),
    ],
)
def test_company_site_fallback(url: str, domain: str) -> None:
    kind, dom = classify_apply(url)
    assert kind == "company_site"
    assert dom == domain


# ── Unknown ────────────────────────────────────────────────────────────────

@pytest.mark.parametrize(
    "url",
    ["", "   ", "not a url", "mailto:jobs@acme.com", "ftp://files.acme.com/x",
     "javascript:alert(1)", "/relative/path/only", "https://", "http://:8080/x"],
)
def test_unknown(url: str) -> None:
    kind, dom = classify_apply(url)
    assert kind == "unknown"
    assert dom == ""


# ── Normalization + suffix safety ──────────────────────────────────────────

def test_case_and_www_and_port_normalized() -> None:
    kind, dom = classify_apply("HTTPS://WWW.WUZZUF.NET:443/jobs/p/1")
    assert kind == "aggregator_relay"
    assert dom == "wuzzuf.net"


def test_no_substring_false_positive() -> None:
    # A hostile/lookalike host must not match the ATS table by substring.
    kind, _ = classify_apply("https://boards.greenhouse.io.evil.com/x")
    assert kind == "company_site"
    kind, _ = classify_apply("https://notgreenhouse.io/x")
    assert kind == "company_site"
    kind, _ = classify_apply("https://mylever.co.uk/x")
    assert kind == "company_site"


def test_bare_apex_matches_suffix_table() -> None:
    # A bare apex of a listed ATS domain still counts (host == entry).
    kind, dom = classify_apply("https://greenhouse.io/anything")
    assert kind == "ats"
    assert dom == "greenhouse.io"


def test_userinfo_trick_uses_real_host() -> None:
    # urlsplit().hostname excludes userinfo — "greenhouse.io@evil.com"
    # must classify by the REAL host, never the decoy before the @.
    kind, dom = classify_apply("https://greenhouse.io@evil.com/x")
    assert kind == "company_site"
    assert dom == "evil.com"


def test_trailing_dot_and_deep_subdomain() -> None:
    kind, dom = classify_apply("https://boards.greenhouse.io.:443/x")
    assert (kind, dom) == ("ats", "boards.greenhouse.io")
    kind, _ = classify_apply("https://sub.jobs.lever.co/x")
    assert kind == "ats"


def test_ipv6_and_dotless_hosts_unknown() -> None:
    assert classify_apply("https://[2001:db8::1]/apply").kind == "unknown"
    assert classify_apply("https://localhost/x").kind == "unknown"


def test_backslash_parser_differential() -> None:
    # Browsers (WHATWG) treat "\" as "/" in http(s) URLs; urlsplit does not.
    # Without normalization this URL classifies by the decoy ATS host while
    # a browser navigates to evil.com. Review-pinned (P5 correctness lane).
    kind, dom = classify_apply("https://evil.com\\@greenhouse.io/x")
    assert kind == "company_site"
    assert dom == "evil.com"


def test_non_dns_hosts_unknown() -> None:
    # Unicode / percent-junk hosts never reach a trusted bucket.
    assert classify_apply("https://münchen.de/jobs").kind == "unknown"
    assert classify_apply("https://foo%00bar.com/x").kind == "unknown"


def test_enterprise_ats_additions() -> None:
    assert classify_apply("https://career5.successfactors.eu/x").kind == "ats"
    assert classify_apply("https://jpmc.fa.oraclecloud.com/hcmUI/x").kind == "ats"


def test_auto_submit_subset_is_within_ats_table() -> None:
    # P6 contract: assisted submission may only key on this subset, and the
    # subset must stay inside the ATS table (review-pinned).
    from jobhunt.apply_target import _ATS_DOMAINS, AUTO_SUBMIT_DOMAINS

    assert AUTO_SUBMIT_DOMAINS <= _ATS_DOMAINS
    assert "taleo.net" not in AUTO_SUBMIT_DOMAINS
    assert "myworkdayjobs.com" not in AUTO_SUBMIT_DOMAINS
