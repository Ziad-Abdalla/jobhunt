from __future__ import annotations

import logging
from collections.abc import Iterator
from contextlib import contextmanager

from sqlalchemy import create_engine, event, inspect, text
from sqlalchemy.orm import Session, sessionmaker

from .config import settings
from .models import Base

log = logging.getLogger(__name__)

# SQLite gets locked when multiple writers contend (e.g. the category
# backfill background thread vs an incoming request). A 30s busy-timeout
# makes the second writer wait quietly instead of raising
# OperationalError("database is locked"). WAL journal mode lets readers
# proceed concurrently with that one writer — strictly better for our
# read-heavy + occasional-bulk-write workload.
_engine = create_engine(
    settings.db_url,
    future=True,
    connect_args={"timeout": 30, "check_same_thread": False},
)


@event.listens_for(_engine, "connect")
def _set_sqlite_pragmas(dbapi_connection, _record):  # type: ignore[no-untyped-def]
    cur = dbapi_connection.cursor()
    cur.execute("PRAGMA journal_mode=WAL")
    cur.execute("PRAGMA synchronous=NORMAL")  # safe with WAL, faster commits
    cur.execute("PRAGMA busy_timeout=30000")
    cur.close()


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


_FTS_AVAILABLE: bool | None = None


def has_fts5() -> bool:
    """True when the SQLite build supports FTS5 (it does in every wheel
    Python ships on macOS/Windows/Linux since 3.7). Cached after first call."""
    global _FTS_AVAILABLE
    if _FTS_AVAILABLE is not None:
        return _FTS_AVAILABLE
    try:
        with _engine.begin() as conn:
            conn.execute(text(
                "CREATE VIRTUAL TABLE IF NOT EXISTS _fts5_probe "
                "USING fts5(x)"
            ))
            conn.execute(text("DROP TABLE _fts5_probe"))
        _FTS_AVAILABLE = True
    except Exception:  # noqa: BLE001
        _FTS_AVAILABLE = False
    return _FTS_AVAILABLE


def _setup_fts() -> None:
    """Create the jobs_fts virtual table + sync triggers. Idempotent.

    Schema: a 3-column FTS5 index over (title, company, description), with
    `content='jobs'` so we don't double-store the text — FTS5 just maintains
    the inverted index that points back at the jobs rowid. Triggers keep it
    in sync on INSERT / UPDATE / DELETE. On first setup we bulk-rebuild from
    the existing rows."""
    if not has_fts5():
        log.info("SQLite build lacks FTS5; keyword search will use LIKE")
        return

    insp = inspect(_engine)
    if not insp.has_table("jobs"):
        return

    with _engine.begin() as conn:
        # Virtual table (FTS5 doesn't show up in insp.has_table reliably
        # — use sqlite_master directly).
        existing = conn.execute(text(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='jobs_fts'"
        )).scalar_one_or_none()
        if not existing:
            conn.execute(text(
                "CREATE VIRTUAL TABLE jobs_fts USING fts5("
                "title, company, description, content='jobs', content_rowid='id', "
                "tokenize='porter unicode61'"
                ")"
            ))
            # Bulk-rebuild from existing rows.
            conn.execute(text(
                "INSERT INTO jobs_fts(rowid, title, company, description) "
                "SELECT id, title, company, description FROM jobs"
            ))
            log.info("FTS5 index built over jobs table")

        # Triggers — idempotent CREATE IF NOT EXISTS.
        conn.execute(text("""
            CREATE TRIGGER IF NOT EXISTS jobs_ai AFTER INSERT ON jobs BEGIN
              INSERT INTO jobs_fts(rowid, title, company, description)
              VALUES (new.id, new.title, new.company, new.description);
            END;
        """))
        conn.execute(text("""
            CREATE TRIGGER IF NOT EXISTS jobs_ad AFTER DELETE ON jobs BEGIN
              INSERT INTO jobs_fts(jobs_fts, rowid, title, company, description)
              VALUES('delete', old.id, old.title, old.company, old.description);
            END;
        """))
        conn.execute(text("""
            CREATE TRIGGER IF NOT EXISTS jobs_au AFTER UPDATE ON jobs BEGIN
              INSERT INTO jobs_fts(jobs_fts, rowid, title, company, description)
              VALUES('delete', old.id, old.title, old.company, old.description);
              INSERT INTO jobs_fts(rowid, title, company, description)
              VALUES (new.id, new.title, new.company, new.description);
            END;
        """))


def wal_checkpoint() -> None:
    """Roll the WAL file back into the main database to keep its size
    bounded. PASSIVE mode never blocks readers and skips if any other
    connection is mid-transaction — safe to call on every refresh."""
    try:
        with _engine.begin() as conn:
            conn.execute(text("PRAGMA wal_checkpoint(PASSIVE)"))
    except Exception as exc:  # noqa: BLE001
        log.debug("wal_checkpoint skipped: %s", exc)


def init_db() -> None:
    _apply_forward_migrations()
    Base.metadata.create_all(_engine)
    _normalize_employment_types()
    _setup_fts()
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
