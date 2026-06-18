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

    sources_file: Path = Field(default_factory=lambda: _find_sources_yaml())
    local_sources_file: Path = Field(default_factory=lambda: _PLATFORM_DATA / "local_sources.yaml")

    host: str = "127.0.0.1"
    port: int = 8765

    refresh_interval_minutes: int = 0
    notify_method: str = "auto"
    notify_batch_max: int = 5

    jooble_api_key: str = ""
    reed_api_key: str = ""

    # User's location — when set, Jooble automatically fetches local jobs for this area.
    # Examples: "London, UK", "Berlin, Germany", "Cairo, Egypt", "Sydney, Australia"
    # Reed also scopes every search to this town + reed_distance_miles (server-side
    # distance filter), so results are "near me" rather than UK-wide.
    user_location: str = ""

    # Travel radius (miles) used by Reed's distanceFromLocation when user_location
    # is set. Generous default so it covers a whole city plus commuter towns.
    reed_distance_miles: int = 15

    @property
    def db_url(self) -> str:
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        return f"sqlite:///{self.db_path}"

    @property
    def data_dir(self) -> Path:
        return self.db_path.parent


settings = Settings()
