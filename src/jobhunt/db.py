from __future__ import annotations

import hashlib
import logging
import re
import threading
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
        (
            "geo_restrict",
            "ALTER TABLE jobs ADD COLUMN geo_restrict VARCHAR(24) DEFAULT 'unknown'",
        ),
        # P5: nullable on purpose — NULL marks "not yet classified" for the
        # one-time backfill; _persist writes a value on every insert/update.
        ("apply_kind", "ALTER TABLE jobs ADD COLUMN apply_kind VARCHAR(16)"),
        ("apply_domain", "ALTER TABLE jobs ADD COLUMN apply_domain VARCHAR(256) DEFAULT ''"),
    ],
    "scrape_runs": [
        ("board", "ALTER TABLE scrape_runs ADD COLUMN board VARCHAR(128) DEFAULT ''"),
    ],
    # Full-auto apply (2026-07-22): the cowork tables predate these columns
    # on live DBs, so create_all skips them — only ALTER reaches them.
    "applicant_profile": [
        (
            "cv_path_egypt",
            "ALTER TABLE applicant_profile ADD COLUMN cv_path_egypt VARCHAR(512) DEFAULT ''",
        ),
        (
            "cv_path_remote",
            "ALTER TABLE applicant_profile ADD COLUMN cv_path_remote VARCHAR(512) DEFAULT ''",
        ),
        (
            "notice_period",
            "ALTER TABLE applicant_profile ADD COLUMN notice_period VARCHAR(128) DEFAULT ''",
        ),
        (
            "earliest_start",
            "ALTER TABLE applicant_profile ADD COLUMN earliest_start VARCHAR(128) DEFAULT ''",
        ),
        (
            "how_heard_default",
            "ALTER TABLE applicant_profile ADD COLUMN how_heard_default VARCHAR(128) DEFAULT ''",
        ),
        (
            "eeo_default",
            "ALTER TABLE applicant_profile "
            "ADD COLUMN eeo_default VARCHAR(128) DEFAULT 'Prefer not to say'",
        ),
    ],
    "applications": [
        ("queued_by", "ALTER TABLE applications ADD COLUMN queued_by VARCHAR(8) DEFAULT 'human'"),
        ("annotations", "ALTER TABLE applications ADD COLUMN annotations JSON"),
        ("outcome", "ALTER TABLE applications ADD COLUMN outcome VARCHAR(24) DEFAULT ''"),
        ("outcome_note", "ALTER TABLE applications ADD COLUMN outcome_note TEXT DEFAULT ''"),
        ("outcome_updated_at", "ALTER TABLE applications ADD COLUMN outcome_updated_at DATETIME"),
    ],
}


# `ALTER TABLE … ADD COLUMN` doesn't create the model's column index on an
# UPGRADED database (create_all skips existing tables), so indexed forward
# columns need explicit DDL. geo_restrict shipped in P3 without this — the
# statement below repairs upgraded installs on next boot.
_FORWARD_INDEXES: list[str] = [
    "CREATE INDEX IF NOT EXISTS ix_jobs_geo_restrict ON jobs (geo_restrict)",
    "CREATE INDEX IF NOT EXISTS ix_jobs_apply_kind ON jobs (apply_kind)",
]


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
        for ddl in _FORWARD_INDEXES:
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

# user_version bit flags (SQLite PRAGMA, one integer for the whole DB).
# Bit 0 belongs to the P3 fingerprint migration; bit 1 records that the
# category backfill completed one full pass over legacy 'other' rows.
# Always set bits via _set_user_version_bit (read-modify-write) — a blind
# `PRAGMA user_version = n` would clobber the other owner's flag.
_UV_REFINGERPRINT_DONE = 1
_UV_CATEGORY_DONE = 2


def _get_user_version() -> int:
    with _engine.begin() as conn:
        return conn.execute(text("PRAGMA user_version")).scalar_one()


# Serializes read-modify-write on the PRAGMA within this process: the
# category-backfill worker thread and startup code can otherwise interleave
# reads and lose a freshly-set bit (observed as a test-suite race). A lost
# set would only mean benign re-work next boot, but cheap correctness wins.
_user_version_lock = threading.Lock()


def _set_user_version_bit(bit: int) -> None:
    with _user_version_lock, _engine.begin() as conn:
        version = conn.execute(text("PRAGMA user_version")).scalar_one()
        conn.execute(text(f"PRAGMA user_version = {version | bit}"))


def _category_pending_where(version: int) -> str:
    """Rows the category backfill still needs to visit.

    'other' is both the legacy column default AND a legitimate
    classification result, so rows classified as 'other' are
    indistinguishable from never-visited ones by value alone. Until one
    full pass completes (user_version bit), every 'other' row is scanned;
    afterwards only NULL/'' rows (which _persist never writes) are.
    Observed live before this gate: the same 18,826 'other' rows re-queued
    on every boot, churning the DB ('database is locked' in the log)."""
    if version & _UV_CATEGORY_DONE:
        return "category IS NULL OR category = ''"
    return "category IS NULL OR category = 'other' OR category = ''"


def _backfill_chunk_once(where: str, after_id: int) -> tuple[int, int]:
    """Classify up to _BACKFILL_CHUNK rows with id > after_id. Returns
    (rows processed, last id visited). The id cursor guarantees forward
    progress: a row re-classified as 'other' stays in the WHERE set, and
    without the cursor the same first chunk would be selected forever."""
    from .extract import classify_category

    with _engine.begin() as conn:
        rows = conn.execute(
            text(
                f"SELECT id, title, description FROM jobs "
                f"WHERE ({where}) AND id > :after ORDER BY id LIMIT :limit"
            ),
            {"after": after_id, "limit": _BACKFILL_CHUNK},
        ).fetchall()
        if not rows:
            return 0, after_id
        for row_id, title, description in rows:
            cat = classify_category(title or "", description or "")
            conn.execute(
                text("UPDATE jobs SET category = :cat WHERE id = :id"),
                {"cat": cat or "other", "id": row_id},
            )
    return len(rows), rows[-1][0]


def _backfill_categories_async(where: str) -> None:
    """Background worker: scan + classify in chunks until done. Each chunk
    is its own transaction so /local can serve requests while we work.
    A completed pass sets the user_version flag so later boots skip the
    legacy full scan; a crash leaves the flag unset and the pass re-runs."""
    cursor = 0
    while True:
        try:
            n, cursor = _backfill_chunk_once(where, cursor)
        except Exception as exc:  # noqa: BLE001
            log.warning("category backfill chunk failed: %s", exc)
            return
        if n < _BACKFILL_CHUNK:
            log.info("category backfill: finished")
            try:
                _set_user_version_bit(_UV_CATEGORY_DONE)
            except Exception as exc:  # noqa: BLE001
                log.warning("category backfill: flag write failed: %s", exc)
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
        version = conn.execute(text("PRAGMA user_version")).scalar_one()
        where = _category_pending_where(version)
        remaining = conn.execute(
            text(f"SELECT COUNT(*) FROM jobs WHERE {where}")
        ).scalar_one()
    if not remaining:
        # An empty legacy scan still counts as a completed pass.
        if not version & _UV_CATEGORY_DONE:
            _set_user_version_bit(_UV_CATEGORY_DONE)
        return

    import threading

    log.info("category backfill: %d rows queued (background)", remaining)
    threading.Thread(
        target=_backfill_categories_async,
        args=(where,),
        daemon=True,
        name="jobhunt-backfill",
    ).start()
    _BACKFILL_THREAD_STARTED = True


# ── P5: one-time apply-target backfill ────────────────────────────────────
# Pre-P5 rows have apply_kind NULL (the forward ALTER adds the column with
# no default). The backfill rewrites NULL → classify_apply(url), writing
# 'unknown' explicitly so a row is never revisited. Self-gating: once no
# NULLs remain there is nothing to scan — no user_version coupling with the
# P3 refingerprint gate (which retries on failure and owns that counter).
#
# Known trade-offs (shared with the category backfill, accepted): the
# started-flag latches for the process lifetime even if a chunk fails
# (remaining NULLs read as 'unknown' via coalesce until the next boot
# resumes them), and a _persist update committing between a chunk's SELECT
# and UPDATE can be transiently overwritten with the same-URL classification
# (self-heals on the next scrape).

_APPLY_BACKFILL_THREAD_STARTED = False


def _apply_backfill_chunk_once() -> int:
    """Classify up to _BACKFILL_CHUNK NULL-apply_kind rows. Returns rows done."""
    from .apply_target import classify_apply

    with _engine.begin() as conn:
        rows = conn.execute(
            text(
                "SELECT id, url FROM jobs WHERE apply_kind IS NULL LIMIT :limit"
            ),
            {"limit": _BACKFILL_CHUNK},
        ).fetchall()
        if not rows:
            return 0
        for row_id, url in rows:
            kind, domain = classify_apply(url or "")
            conn.execute(
                text(
                    "UPDATE jobs SET apply_kind = :kind, apply_domain = :domain "
                    "WHERE id = :id"
                ),
                {"kind": kind, "domain": domain, "id": row_id},
            )
    return len(rows)


def _apply_backfill_async() -> None:
    while True:
        try:
            n = _apply_backfill_chunk_once()
        except Exception as exc:  # noqa: BLE001
            log.warning("apply-target backfill chunk failed: %s", exc)
            return
        if n < _BACKFILL_CHUNK:
            log.info("apply-target backfill: finished")
            return


def _maybe_start_apply_backfill() -> None:
    """Kick off the apply-target backfill in the background when any NULL
    rows remain. Same never-block-boot pattern as the category backfill."""
    global _APPLY_BACKFILL_THREAD_STARTED
    if _APPLY_BACKFILL_THREAD_STARTED:
        return

    insp = inspect(_engine)
    if not insp.has_table("jobs"):
        return
    with _engine.begin() as conn:
        remaining = conn.execute(
            text("SELECT COUNT(*) FROM jobs WHERE apply_kind IS NULL")
        ).scalar_one()
    if not remaining:
        return

    import threading

    log.info("apply-target backfill: %d rows queued (background)", remaining)
    threading.Thread(
        target=_apply_backfill_async,
        daemon=True,
        name="jobhunt-apply-backfill",
    ).start()
    _APPLY_BACKFILL_THREAD_STARTED = True


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


# ---------------------------------------------------------------------------
# One-time fingerprint migration (P3). dedup normalization became
# Unicode-aware + NFC; stored fingerprints for rows containing non-ASCII
# text no longer match what _persist computes, which would duplicate those
# jobs until the stale sweep caught the old rows. This pass rewrites them
# once, gated on PRAGMA user_version (0 = pending, >=1 = done).
#
# The legacy normalization below is a FROZEN copy of the pre-P3 dedup code —
# deliberately not imported from dedup.py, which has moved on. It's needed to
# recognize old-scheme fingerprints, both plain and P1-salted (source_id).
# ---------------------------------------------------------------------------

_LEGACY_WS = re.compile(r"\s+")
_LEGACY_NON_ALNUM = re.compile(r"[^a-z0-9 ]+")


def _legacy_norm_title(title: str) -> str:
    t = title.lower()
    t = re.sub(r"\(.*?\)", " ", t)
    t = re.sub(r"\[.*?\]", " ", t)
    t = re.sub(
        r"\b(sr\.?|senior|jr\.?|junior|staff|principal|lead|"
        r"intern|internship|new grad|entry[- ]level)\b",
        " ", t,
    )
    t = re.sub(r"\b(remote|hybrid|onsite|on[- ]site)\b", " ", t)
    t = _LEGACY_NON_ALNUM.sub(" ", t)
    return _LEGACY_WS.sub(" ", t).strip()


def _legacy_norm_company(company: str) -> str:
    c = company.lower()
    c = re.sub(r"\b(inc|llc|ltd|gmbh|sa|sas|plc|corp|corporation)\b\.?", "", c)
    c = _LEGACY_NON_ALNUM.sub(" ", c)
    return _LEGACY_WS.sub(" ", c).strip()


_LEGACY_REMOTE_SYNONYMS = frozenset({
    "remote", "anywhere", "worldwide", "global", "distributed",
    "fully remote", "remote worldwide", "remote global", "remote anywhere",
    "anywhere in the world", "fully distributed", "remote first",
    "remote friendly", "work from home", "wfh", "100 remote", "100 remote worldwide",
})


def _legacy_norm_location(location: str) -> str:
    loc = location.lower()
    loc = _LEGACY_NON_ALNUM.sub(" ", loc)
    loc = _LEGACY_WS.sub(" ", loc).strip()
    if loc in _LEGACY_REMOTE_SYNONYMS:
        return "remote"
    return loc


def _legacy_fingerprint(company: str, title: str, location: str, salt: str = "") -> str:
    key = (
        f"{_legacy_norm_company(company)}|{_legacy_norm_title(title)}"
        f"|{_legacy_norm_location(location)}"
    )
    if salt:
        key = f"{key}|{salt}"
    return hashlib.sha256(key.encode("utf-8")).hexdigest()[:32]


def _refingerprint_once() -> int:
    """Rewrite old-scheme fingerprints to the new normalization. Returns the
    number of rows changed. Collisions keep the row that already owns the new
    fingerprint (its last_seen_at is bumped) and delete the migrating row."""
    from .dedup import fingerprint as _new_fp

    changed = 0
    with _engine.begin() as conn:
        rows = conn.execute(text(
            "SELECT id, fingerprint, company, title, location, source_id FROM jobs"
        )).fetchall()
        for row_id, stored, company, title, location, source_id in rows:
            company, title, location = company or "", title or "", location or ""
            legacy_plain = _legacy_fingerprint(company, title, location)
            legacy_salted = (
                _legacy_fingerprint(company, title, location, salt=source_id)
                if source_id else None
            )
            if stored == legacy_plain:
                new = _new_fp(company, title, location)
            elif legacy_salted is not None and stored == legacy_salted:
                new = _new_fp(company, title, location, salt=source_id)
            else:
                continue  # unknown provenance or already-new — leave alone
            if new == stored:
                continue
            owner = conn.execute(
                text("SELECT id FROM jobs WHERE fingerprint = :fp AND id != :id"),
                {"fp": new, "id": row_id},
            ).fetchone()
            if owner:
                conn.execute(
                    text("UPDATE jobs SET last_seen_at = MAX(last_seen_at, "
                         "(SELECT last_seen_at FROM jobs WHERE id = :dead)) WHERE id = :keep"),
                    {"dead": row_id, "keep": owner[0]},
                )
                conn.execute(text("DELETE FROM jobs WHERE id = :id"), {"id": row_id})
            else:
                conn.execute(
                    text("UPDATE jobs SET fingerprint = :fp WHERE id = :id"),
                    {"fp": new, "id": row_id},
                )
            changed += 1
    return changed


def _maybe_refingerprint() -> None:
    """Run the fingerprint migration exactly once per database."""
    insp = inspect(_engine)
    if not insp.has_table("jobs"):
        return
    if _get_user_version() & _UV_REFINGERPRINT_DONE:
        return
    try:
        n = _refingerprint_once()
        log.info("fingerprint migration: %d rows rewritten", n)
    except Exception as exc:  # noqa: BLE001 — degrade to temporary dupes, never block boot
        log.warning("fingerprint migration failed (will retry next boot): %s", exc)
        return
    _set_user_version_bit(_UV_REFINGERPRINT_DONE)


def check_integrity() -> tuple[bool, str]:
    """Run SQLite's built-in `PRAGMA integrity_check`. Cheap on small
    databases, slower on multi-GB ones. Returns (ok, message). Used by
    `jobhunt doctor` and as a startup sanity check."""
    try:
        with _engine.begin() as conn:
            result = conn.execute(text("PRAGMA integrity_check")).fetchone()
        msg = result[0] if result else "no result"
        return (msg == "ok", msg)
    except Exception as exc:  # noqa: BLE001
        return (False, f"{type(exc).__name__}: {exc}")


def init_db() -> None:
    # Register the PII tables (own module — see the P6 import guard) with
    # Base.metadata before create_all. db.py is NOT part of the scrape
    # pipeline, so this import doesn't weaken the locality gate.
    from . import cowork_models  # noqa: F401

    _apply_forward_migrations()
    Base.metadata.create_all(_engine)
    _normalize_employment_types()
    _maybe_refingerprint()
    _setup_fts()
    _maybe_start_backfill()
    _maybe_start_apply_backfill()


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
