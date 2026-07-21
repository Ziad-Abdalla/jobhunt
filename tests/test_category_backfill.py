"""Category-backfill one-time gating.

Observed live (jobhunt.log, 2026-07-21): the backfill re-queued the same
18,826 category='other' rows on every startup — the promised '_done'
sentinel was never implemented, so classified-as-'other' rows matched the
needs-visit predicate forever (startup churn + 'database is locked'
contention). The fix gates the legacy full scan on a user_version bit:
once a full pass completes, later boots only visit NULL/'' rows.
"""

from __future__ import annotations

from sqlalchemy import text

import jobhunt.db as db_mod
from jobhunt.db import (
    _UV_CATEGORY_DONE,
    _UV_REFINGERPRINT_DONE,
    _category_pending_where,
    _set_user_version_bit,
    init_db,
)


def test_pending_where_full_scan_before_flag():
    where = _category_pending_where(0)
    assert "category = 'other'" in where
    assert "category IS NULL" in where


def test_pending_where_narrow_after_flag():
    where = _category_pending_where(_UV_CATEGORY_DONE)
    assert "category = 'other'" not in where
    assert "category IS NULL" in where


def test_flag_bits_are_distinct():
    assert _UV_REFINGERPRINT_DONE & _UV_CATEGORY_DONE == 0


def test_set_user_version_bit_preserves_other_bits():
    """Read-modify-write: setting one flag must never clobber another
    (the refingerprint gate owns bit 0). Uses a high scratch bit and
    restores the original value.

    NOTE: reference db_mod._engine dynamically — an earlier test
    (test_category) rebinds it to a temp DB without restoring, and a
    from-import captured at collection time would read a DIFFERENT
    database than _set_user_version_bit writes to."""
    init_db()
    scratch = 1 << 20
    with db_mod._engine.begin() as conn:
        original = conn.execute(text("PRAGMA user_version")).scalar_one()
    try:
        _set_user_version_bit(scratch)
        with db_mod._engine.begin() as conn:
            now = conn.execute(text("PRAGMA user_version")).scalar_one()
        assert now & scratch
        # The invariant is "never CLEARS another owner's bit". A concurrent
        # background worker may legitimately SET one meanwhile, so don't
        # assert exact equality — only that no originally-set bit was lost.
        assert (now & original) == original
    finally:
        with db_mod._engine.begin() as conn:
            restore = conn.execute(text("PRAGMA user_version")).scalar_one() & ~scratch
            conn.execute(text(f"PRAGMA user_version = {restore}"))
