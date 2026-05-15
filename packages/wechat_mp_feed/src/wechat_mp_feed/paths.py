"""Filesystem path helpers for mpfeed."""

from __future__ import annotations

import os
from pathlib import Path

HOME_ENV = "WECHAT_MP_FEED_HOME"
DB_ENV = "WECHAT_MP_FEED_DB"


def default_home() -> Path:
    """Return the user-specific mpfeed home directory."""
    return Path(os.environ.get(HOME_ENV, "~/.wechat-mp-feed")).expanduser()


def default_db_path() -> Path:
    """Return the default SQLite database path."""
    configured = os.environ.get(DB_ENV)
    if configured:
        return Path(configured).expanduser()
    return default_home() / "mpfeed.sqlite"


def resolve_db_path(path: str | None) -> Path:
    """Resolve an explicit path or fall back to environment/default config."""
    return Path(path).expanduser() if path else default_db_path()


def ensure_parent(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
