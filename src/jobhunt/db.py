from __future__ import annotations

import logging
from collections.abc import Iterator
from contextlib import contextmanager

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import Session, sessionmaker

from .config import settings
from .models import Base

log = logging.getLogger(__name__)

_engine = create_engine(settings.db_url, future=True)
_SessionLocal = sessionmaker(bind=_engine, expire_on_commit=False, future=True)


# Forward-only column additions. Keyed by table → list of (column_name, ddl).
# SQLite-friendly; only `ALTER TABLE … ADD COLUMN`.
_FORWARD_COLUMNS: dict[str, list[tuple[str, str]]] = {
    "jobs": [
        ("cv_match", "ALTER TABLE jobs ADD COLUMN cv_match FLOAT"),
        (
            "employment_type",
            "ALTER TABLE jobs ADD COLUMN employment_type VARCHAR(32) DEFAULT 'unknown'",
        ),
        ("salary_min", "ALTER TABLE jobs ADD COLUMN salary_min INTEGER"),
        ("salary_max", "ALTER TABLE jobs ADD COLUMN salary_max INTEGER"),
        ("salary_currency", "ALTER TABLE jobs ADD COLUMN salary_currency VARCHAR(8) DEFAULT ''"),
        ("salary_estimated", "ALTER TABLE jobs ADD COLUMN salary_estimated BOOLEAN DEFAULT 0"),
        ("visa_sponsorship", "ALTER TABLE jobs ADD COLUMN visa_sponsorship VARCHAR(32) DEFAULT 'unknown'"),
        ("category", "ALTER TABLE jobs ADD COLUMN category VARCHAR(16) DEFAULT 'other'"),
    ],
    "scrape_runs": [
        ("board", "ALTER TABLE scrape_runs ADD COLUMN board VARCHAR(128) DEFAULT ''"),
    ],
}


def _apply_forward_migrations() -> None:
    insp = inspect(_engine)
    if not insp.has_table("jobs"):
        return  # fresh DB — create_all just made everything
    with _engine.begin() as conn:
        for table, additions in _FORWARD_COLUMNS.items():
            if not insp.has_table(table):
                continue
            existing = {c["name"] for c in insp.get_columns(table)}
            for col_name, ddl in additions:
                if col_name not in existing:
                    log.info("migrating: %s", ddl)
                    conn.execute(text(ddl))


def _normalize_employment_types() -> None:
    """One-time pass: normalize messy employment_type values in existing rows."""
    from .refresh import _EMPLOYMENT_TYPE_MAP

    insp = inspect(_engine)
    if not insp.has_table("jobs"):
        return
    with _engine.begin() as conn:
        rows = conn.execute(
            text("SELECT DISTINCT employment_type FROM jobs")
        ).all()
        for (raw,) in rows:
            if not raw:
                continue
            normalized = _EMPLOYMENT_TYPE_MAP.get(raw.lower().strip(), None)
            if normalized and normalized != raw:
                conn.execute(
                    text("UPDATE jobs SET employment_type = :new WHERE employment_type = :old"),
                    {"new": normalized, "old": raw},
                )


_BACKFILL_CHUNK = 500
_BACKFILL_THREAD_STARTED = False
# We use 'other' as the default value; once the backfill has visited a row
# we mark it with the explicit sentinel '_done' (rewritten to 'other' when the
# row really has no signal). This avoids re-scanning the same rows every boot.
_BACKFILL_NEEDS_VISIT = (
    "category IS NULL OR category = 'other' OR category = ''"
)


def _backfill_chunk_once() -> int:
    """Classify up to _BACKFILL_CHUNK rows. Returns the number processed."""
    from .extract import classify_category

    with _engine.begin() as conn:
        rows = conn.execute(
            text(
                f"SELECT id, title, description FROM jobs "
                f"WHERE {_BACKFILL_NEEDS_VISIT} LIMIT :limit"
            ),
            {"limit": _BACKFILL_CHUNK},
        ).fetchall()
        if not rows:
            return 0
        for row_id, title, description in rows:
            cat = classify_category(title or "", description or "")
            # Write 'other' explicitly so we don't re-pick the row next chunk.
            conn.execute(
                text("UPDATE jobs SET category = :cat WHERE id = :id"),
                {"cat": cat or "other", "id": row_id},
            )
    return len(rows)


def _backfill_categories_async() -> None:
    """Background worker: scan + classify in chunks until done. Each chunk
    is its own transaction so /local can serve requests while we work."""
    while True:
        try:
            n = _backfill_chunk_once()
        except Exception as exc:  # noqa: BLE001
            log.warning("category backfill chunk failed: %s", exc)
            return
        if n < _BACKFILL_CHUNK:
            log.info("category backfill: finished")
            return


def _maybe_start_backfill() -> None:
    """Decide whether existing 'other' rows need classifying, and if so kick
    off a background thread. Startup never blocks on the backfill — a fresh
    install with no jobs is a no-op, and a multi-thousand-row upgrade still
    boots in <1 second while the backfill runs lazily."""
    global _BACKFILL_THREAD_STARTED
    if _BACKFILL_THREAD_STARTED:
        return

    insp = inspect(_engine)
    if not insp.has_table("jobs"):
        return
    # Cheap pre-check — the count below is fast even on a 100k-row DB.
    with _engine.begin() as conn:
        remaining = conn.execute(
            text(f"SELECT COUNT(*) FROM jobs WHERE {_BACKFILL_NEEDS_VISIT}")
        ).scalar_one()
    if not remaining:
        return

    import threading

    log.info("category backfill: %d rows queued (background)", remaining)
    threading.Thread(
        target=_backfill_categories_async,
        daemon=True,
        name="jobhunt-backfill",
    ).start()
    _BACKFILL_THREAD_STARTED = True


def init_db() -> None:
    _apply_forward_migrations()
    Base.metadata.create_all(_engine)
    _normalize_employment_types()
    _maybe_start_backfill()


@contextmanager
def db_session() -> Iterator[Session]:
    s = _SessionLocal()
    try:
        yield s
        s.commit()
    except Exception:
        s.rollback()
        raise
    finally:
        s.close()
