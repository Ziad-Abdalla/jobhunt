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


def init_db() -> None:
    _apply_forward_migrations()
    Base.metadata.create_all(_engine)


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
