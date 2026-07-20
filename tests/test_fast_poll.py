"""P7: fast-poll scheduler tier + only_sources scrape scoping."""

from __future__ import annotations

import asyncio

import pytest

from jobhunt.alerts import collect_priority_sources
from jobhunt.config import settings
from jobhunt.db import db_session, init_db
from jobhunt.models import SavedSearch
from jobhunt.refresh import scrape_all


@pytest.fixture(autouse=True)
def _clean():
    init_db()
    with db_session() as s:
        s.query(SavedSearch).filter(SavedSearch.name.like("FastPoll%")).delete()
    yield
    with db_session() as s:
        s.query(SavedSearch).filter(SavedSearch.name.like("FastPoll%")).delete()


def test_only_sources_filters_to_nothing_without_network():
    # A non-existent source filters every spec out → scrape returns 0 sources
    # and never touches the network (proves the filter runs before fetch).
    result = asyncio.run(scrape_all(only_sources={"no-such-source-xyz"}))
    assert result["sources"] == 0


def test_collect_priority_sources_unions_priority_searches():
    with db_session() as s:
        s.add(SavedSearch(
            name="FastPoll a", notify=True, notified_job_ids=[],
            query_json={"priority": True, "sources": ["wuzzuf", "remotive"]},
        ))
        s.add(SavedSearch(
            name="FastPoll b", notify=True, notified_job_ids=[],
            query_json={"priority": True, "sources": ["wuzzuf", "greenhouse"]},
        ))
        s.add(SavedSearch(  # not priority → ignored
            name="FastPoll c", notify=True, notified_job_ids=[],
            query_json={"priority": False, "sources": ["lever"]},
        ))
        s.add(SavedSearch(  # priority but no sources → contributes nothing
            name="FastPoll d", notify=True, notified_job_ids=[],
            query_json={"priority": True},
        ))
    assert collect_priority_sources() == {"wuzzuf", "remotive", "greenhouse"}


def test_fast_poll_off_by_default():
    assert settings.fast_poll_minutes == 0


def test_only_sources_excludes_jooble_autoappend(monkeypatch):
    # The Jooble location auto-append must NOT fire on a fast-poll pass that
    # didn't ask for jooble (else the tight interval hammers Jooble's API).
    monkeypatch.setattr(settings, "user_location", "Cairo, Egypt")
    monkeypatch.setattr(settings, "jooble_api_key", "k")
    appended = []
    import jobhunt.refresh as refresh_mod
    real_gather = refresh_mod.asyncio.gather

    async def _spy_gather(*coros, **kw):
        appended.append(len(coros))
        return []

    monkeypatch.setattr(refresh_mod.asyncio, "gather", _spy_gather)
    # only_sources without jooble → no jooble specs added; a non-existent
    # source means zero specs, so scrape_all returns before gather.
    result = asyncio.run(scrape_all(only_sources={"no-such-source"}))
    monkeypatch.setattr(refresh_mod.asyncio, "gather", real_gather)
    assert result["sources"] == 0  # jooble was NOT appended past the filter
