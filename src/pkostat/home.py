"""The PKOSTAT_HOME layout: folders, .env template, database."""

import sqlite3
from contextlib import closing
from dataclasses import dataclass
from pathlib import Path

from pkostat.categorize.config import CATEGORIES_FILE, RULES_FILE, default_text
from pkostat.config import ENV_TEMPLATE, Settings
from pkostat.db.connection import connect
from pkostat.db.migrate import current_version, migrate
from pkostat.errors import PkoStatError


@dataclass(frozen=True, slots=True)
class InitResult:
    created_env: bool
    created_configs: list[str]
    applied_migrations: list[str]
    schema_version: int


def init_home(settings: Settings) -> InitResult:
    for folder in (settings.db_path.parent, settings.reports_dir, settings.backups_dir):
        folder.mkdir(parents=True, exist_ok=True)
    created_env = _write_if_missing(settings.env_path, ENV_TEMPLATE)
    created_configs = [
        name
        for name in (CATEGORIES_FILE, RULES_FILE)
        if _write_if_missing(settings.home / name, default_text(name))
    ]
    with closing(connect(settings.db_path)) as conn:
        applied = migrate(conn)
        version = current_version(conn)
    return InitResult(created_env, created_configs, applied, version)


def open_database(settings: Settings) -> sqlite3.Connection:
    """Open the existing database, applying any migrations added since it was created."""
    if not settings.db_path.is_file():
        raise PkoStatError(f"No database at {settings.db_path}. Run `pkostat init` first.")
    conn = connect(settings.db_path)
    try:
        migrate(conn)
    except PkoStatError:
        conn.close()
        raise
    return conn


def _write_if_missing(path: Path, text: str) -> bool:
    # Never overwrite: existing files hold the user's secrets and edits.
    if path.exists():
        return False
    path.write_text(text, encoding="utf-8")
    return True
