"""Schema migrations: numbered SQL files applied in order, tracked by PRAGMA user_version."""

import logging
import re
import sqlite3
from dataclasses import dataclass
from importlib.resources import files

from pkostat.errors import PkoStatError

log = logging.getLogger(__name__)

_FILE_NAME = re.compile(r"^(?P<number>\d{3})_[a-z0-9_]+\.sql$")


@dataclass(frozen=True, slots=True)
class Migration:
    number: int
    name: str
    sql: str


def load_migrations() -> list[Migration]:
    found: list[Migration] = []
    for entry in files("pkostat.db").joinpath("migrations").iterdir():
        match = _FILE_NAME.match(entry.name)
        if match is None:
            continue
        found.append(Migration(int(match["number"]), entry.name, entry.read_text("utf-8")))
    found.sort(key=lambda migration: migration.number)
    expected = list(range(1, len(found) + 1))
    if [migration.number for migration in found] != expected:
        names = ", ".join(migration.name for migration in found)
        raise PkoStatError(f"Migrations must be numbered 001, 002, … without gaps: {names}")
    return found


def current_version(conn: sqlite3.Connection) -> int:
    return conn.execute("PRAGMA user_version").fetchone()[0]


def migrate(conn: sqlite3.Connection) -> list[str]:
    """Apply pending migrations; return the names of the ones applied."""
    migrations = load_migrations()
    version = current_version(conn)
    if version > len(migrations):
        raise PkoStatError(
            f"Database schema version {version} is newer than this code ({len(migrations)}). "
            "Update PkoStat."
        )
    applied: list[str] = []
    for migration in migrations[version:]:
        _apply(conn, migration)
        applied.append(migration.name)
        log.info("Applied migration %s", migration.name)
    return applied


def _apply(conn: sqlite3.Connection, migration: Migration) -> None:
    # user_version is set inside the same transaction, so a failed script leaves no trace.
    script = f"BEGIN;\n{migration.sql}\nPRAGMA user_version = {migration.number};\nCOMMIT;"
    try:
        conn.executescript(script)
    except sqlite3.Error as exc:
        if conn.in_transaction:
            conn.rollback()
        raise PkoStatError(f"Migration {migration.name} failed: {exc}") from exc
