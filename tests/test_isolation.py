"""The test suite must NEVER touch the developer's real data dir.

Discovered 2026-07-22 the hard way: without conftest isolation,
test_backup_restore's real `jobhunt backup` → `jobhunt restore` round-trip
rewrote the owner's data-dir `.env` (restore keeps only its env allowlist,
so the JSearch/Careerjet keys and scheduler settings vanished — previously
misdiagnosed as the installed app's write-only Settings save), and
`_clear_searches()` deleted the owner's live saved searches. CI never
caught it because CI starts with no data dir at all.
"""

from __future__ import annotations

import tempfile
from pathlib import Path

from platformdirs import user_data_dir

from jobhunt.config import APP_AUTHOR, APP_NAME, settings


def test_suite_is_isolated_from_real_data_dir():
    platform_data = Path(user_data_dir(APP_NAME, APP_AUTHOR)).resolve()
    data_dir = settings.data_dir.resolve()
    assert not data_dir.is_relative_to(platform_data), (
        f"tests are running against the REAL data dir {platform_data} — "
        "conftest.py must redirect JOBHUNT_DB_PATH before any jobhunt import"
    )
    assert Path(tempfile.gettempdir()).resolve() in data_dir.parents


def test_local_sources_file_is_isolated():
    platform_data = Path(user_data_dir(APP_NAME, APP_AUTHOR)).resolve()
    ls_file = Path(settings.local_sources_file).resolve()
    assert not ls_file.is_relative_to(platform_data), (
        "settings.local_sources_file points at the real data dir — "
        "conftest.py must redirect JOBHUNT_LOCAL_SOURCES_FILE"
    )
