from __future__ import annotations

from pathlib import Path

from platformdirs import user_data_dir
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
APP_NAME = "jobhunt"
APP_AUTHOR = "jobhunt"

# When running from a source checkout we prefer ./data so dev work stays in-repo.
# When installed (pip install / pipx), there's no writable repo, so fall back to
# the OS user-data directory: ~/.local/share/jobhunt on Linux, ~/Library/Application
# Support/jobhunt on macOS, %APPDATA%\jobhunt on Windows.
_REPO_DATA = PROJECT_ROOT / "data"
_PLATFORM_DATA = Path(user_data_dir(APP_NAME, APP_AUTHOR))


def _default_db_path() -> Path:
    if _REPO_DATA.exists() and (PROJECT_ROOT / "pyproject.toml").exists():
        return _REPO_DATA / "jobhunt.db"
    return _PLATFORM_DATA / "jobhunt.db"


_PACKAGE_DIR = Path(__file__).resolve().parent


def _find_sources_yaml() -> Path:
    """Find sources.yaml in source tree, installed package, or PyInstaller bundle."""
    candidates = [
        PROJECT_ROOT / "src" / "jobhunt" / "sources.yaml",
        _PACKAGE_DIR / "sources.yaml",
    ]
    for c in candidates:
        if c.exists():
            return c
    return candidates[-1]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="JOBHUNT_", env_file=".env", extra="ignore")

    db_path: Path = Field(default_factory=_default_db_path)
    user_agent: str = "jobhunt/0.3 (+https://github.com/Abdalla2004-collab/Jobhunt)"
    request_timeout: float = 20.0
    concurrency: int = 4
    stale_after_days: int = 14
    # How often to re-attempt a source that was auto-disabled after 3 straight
    # failures, so a transient outage doesn't kill it forever (self-heal).
    disabled_retry_hours: float = 24.0

    sources_file: Path = Field(default_factory=lambda: _find_sources_yaml())
    local_sources_file: Path = Field(default_factory=lambda: _PLATFORM_DATA / "local_sources.yaml")

    host: str = "127.0.0.1"
    port: int = 8765

    refresh_interval_minutes: int = 0
    notify_method: str = "auto"
    notify_batch_max: int = 5

    # P7: off-machine alert channels. Each self-gates — empty = channel off,
    # so the default is desktop-only (byte-identical to pre-P7).
    telegram_bot_token: str = ""
    telegram_chat_id: str = ""
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""
    smtp_from: str = ""
    smtp_to: str = ""

    # P7 fast-poll tier: when > 0, priority saved searches get a tighter
    # scrape+alert loop over just their sources (0 = off; main interval
    # unchanged).
    fast_poll_minutes: int = 0

    jooble_api_key: str = ""
    reed_api_key: str = ""
    # P8: JSearch (RapidAPI) — the best indirect Egypt/MENA + remote route.
    # BYO-key, off by default; free tier is ~200 req/month so treat it as a
    # low-frequency sweep, not a per-refresh source. Redacted in backups
    # (key name ends in _API_KEY).
    jsearch_api_key: str = ""

    # P6: default-OFF gate for /api/cowork/* (the applicant-data export /
    # write-back used by the Cowork handoff). Even when ON, those endpoints
    # only answer loopback peers. Set JOBHUNT_COWORK_EXPORT=1 to enable.
    cowork_export: bool = False

    # User's location — used two ways: Jooble automatically fetches local jobs
    # for this area, and (P4) ranking demotes jobs geo-restricted to regions
    # you're not in (see scoring.home_region_from_location). Include the
    # country name so the region resolves; unrecognized text never penalizes.
    # Examples: "London, UK", "Berlin, Germany", "Cairo, Egypt", "Sydney, Australia"
    user_location: str = ""

    @property
    def db_url(self) -> str:
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        return f"sqlite:///{self.db_path}"

    @property
    def data_dir(self) -> Path:
        return self.db_path.parent


def _build_settings() -> Settings:
    """The Settings page saves user keys to data_dir/.env, but pydantic only
    auto-reads a CWD .env — so saved keys/location silently vanished on every
    restart. Two-phase load: resolve data_dir with defaults, then re-read with
    the user file included (real env vars still take priority over both)."""
    base = Settings()
    user_env = base.data_dir / ".env"
    if user_env.exists():
        return Settings(_env_file=(".env", str(user_env)))
    return base


settings = _build_settings()
