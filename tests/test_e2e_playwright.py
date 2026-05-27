"""Playwright browser E2E tests. Run with: pytest tests/test_e2e_playwright.py -v

Marked with @pytest.mark.e2e — skipped by default in the main test suite.
Run explicitly: pytest tests/test_e2e_playwright.py -v -m e2e
"""

import threading
import time

import httpx
import pytest
import uvicorn


@pytest.fixture(scope="module")
def server():
    """Start the app server for E2E tests."""
    t = threading.Thread(
        target=lambda: uvicorn.run(
            "jobhunt.main:app", host="127.0.0.1", port=8899, log_level="error",
        ),
        daemon=True,
    )
    t.start()
    for _ in range(20):
        try:
            r = httpx.get("http://127.0.0.1:8899/api/healthz", timeout=2)
            if r.status_code == 200:
                break
        except httpx.ConnectError:
            pass
        time.sleep(0.5)
    yield "http://127.0.0.1:8899"


@pytest.fixture(scope="module")
def browser_page(server):
    """Launch headless Chromium and return a page."""
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        pytest.skip("playwright not installed")

    with sync_playwright() as pw:
        b = pw.chromium.launch(headless=True)
        pg = b.new_page()
        yield pg, server
        b.close()


pytestmark = pytest.mark.e2e


def test_index_loads(browser_page):
    pg, base = browser_page
    pg.goto(base, wait_until="networkidle")
    assert pg.title() == "jobhunt — search"


def test_brand_visible(browser_page):
    pg, base = browser_page
    pg.goto(base, wait_until="networkidle")
    assert "hunt" in (pg.text_content(".brand") or "").lower()


def test_filter_sidebar_exists(browser_page):
    pg, base = browser_page
    pg.goto(base, wait_until="networkidle")
    assert pg.query_selector(".filters") is not None


def test_filter_inputs_present(browser_page):
    pg, base = browser_page
    pg.goto(base, wait_until="networkidle")
    for name in ["q", "company", "location", "min_salary", "max_years", "languages", "skills"]:
        assert pg.query_selector(f'input[name="{name}"]') is not None, f"Missing input: {name}"


def test_filter_fieldsets_present(browser_page):
    pg, base = browser_page
    pg.goto(base, wait_until="networkidle")
    for legend in ["Work mode", "Level", "Degree", "Job type", "Visa sponsorship"]:
        assert pg.query_selector(f'legend:has-text("{legend}")') is not None, f"Missing: {legend}"


def test_job_cards_render(browser_page):
    pg, base = browser_page
    pg.goto(base, wait_until="networkidle")
    pg.wait_for_selector(".card", timeout=15000)
    cards = pg.query_selector_all(".card")
    assert len(cards) > 0


def test_card_structure(browser_page):
    pg, base = browser_page
    pg.goto(base, wait_until="networkidle")
    pg.wait_for_selector(".card", timeout=15000)
    card = pg.query_selector(".card")
    for sel in [".title", ".company", ".score", ".apply-link", ".source"]:
        assert card.query_selector(sel) is not None, f"Card missing {sel}"


def test_job_links_valid(browser_page):
    pg, base = browser_page
    pg.goto(base, wait_until="networkidle")
    pg.wait_for_selector(".card", timeout=15000)
    links = pg.query_selector_all(".apply-link")
    for link in links[:10]:
        href = link.get_attribute("href") or ""
        assert href.startswith("http"), f"Invalid link: {href}"


def test_keyword_filter(browser_page):
    pg, base = browser_page
    pg.goto(base, wait_until="networkidle")
    pg.wait_for_selector(".card", timeout=15000)
    pg.fill('input[name="q"]', "python")
    pg.wait_for_timeout(2000)
    assert "matching" in (pg.text_content(".count-line") or "")
    pg.fill('input[name="q"]', "")


def test_all_pages_load(browser_page):
    pg, base = browser_page
    for path in ["/health", "/alerts", "/cv", "/sources"]:
        pg.goto(f"{base}{path}", wait_until="networkidle")
        assert pg.query_selector("h1") is not None, f"Page {path} missing h1"


def test_security_headers(browser_page):
    pg, base = browser_page
    resp = pg.goto(base)
    for h in ["x-content-type-options", "x-frame-options", "content-security-policy", "referrer-policy"]:
        assert h in resp.headers, f"Missing header: {h}"
