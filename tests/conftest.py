"""Suite-wide isolation: redirect the data dir to a per-run temp location.

This MUST run before any `jobhunt` import — `jobhunt.config` builds the
settings singleton and `jobhunt.db` binds the SQLAlchemy engine at import
time. pytest imports conftest.py before collecting test modules, so setting
the env overrides at module level here is early enough.

Why it exists (2026-07-22): without it the suite ran against the
developer's REAL data dir — `jobhunt restore` round-trip tests rewrote the
live `.env` (dropping every key outside restore's allowlist: JSearch /
Careerjet keys, scheduler settings), and saved-search tests deleted the
owner's live saved searches. CI never noticed because CI has no
pre-existing data dir. Pinned by tests/test_isolation.py.
"""

from __future__ import annotations

import os
import tempfile

import pytest

_TEST_DATA_DIR = tempfile.mkdtemp(prefix="jobhunt-test-data-")

# Force, don't setdefault: an inherited real-value env var would defeat the
# isolation just as silently as the missing conftest did.
os.environ["JOBHUNT_DB_PATH"] = os.path.join(_TEST_DATA_DIR, "jobhunt.db")
os.environ["JOBHUNT_LOCAL_SOURCES_FILE"] = os.path.join(
    _TEST_DATA_DIR, "local_sources.yaml"
)


@pytest.fixture(scope="session", autouse=True)
def _init_test_db():
    """Create the schema in the temp DB, as app boot would. Before
    isolation, tests inherited the real DB's schema by accident; a subset
    run (e.g. `pytest tests/test_backup_restore.py`) must not depend on
    another test having imported the app first."""
    from jobhunt.db import init_db

    init_db()

