import sqlite3
from collections.abc import Iterator

import pytest

from pkostat.db.connection import MEMORY, connect
from pkostat.db.migrate import current_version, load_migrations, migrate
from pkostat.errors import PkoStatError

EXPECTED_TABLES = {
    "users",
    "raw_notifications",
    "rejected_notifications",
    "csv_imports",
    "csv_rows",
    "transactions",
    "merchant_rules",
    "transaction_overrides",
    "reports",
}


@pytest.fixture
def conn() -> Iterator[sqlite3.Connection]:
    connection = connect(MEMORY)
    yield connection
    connection.close()


def _tables(conn: sqlite3.Connection) -> set[str]:
    rows = conn.execute("SELECT name FROM sqlite_master WHERE type = 'table'").fetchall()
    return {row["name"] for row in rows}


def test_migrate_creates_schema(conn: sqlite3.Connection) -> None:
    applied = migrate(conn)

    assert applied[0] == "001_initial.sql"
    assert current_version(conn) == len(load_migrations())
    assert _tables(conn) >= EXPECTED_TABLES


def test_migrate_is_idempotent(conn: sqlite3.Connection) -> None:
    migrate(conn)

    assert migrate(conn) == []


def test_foreign_keys_enforced(conn: sqlite3.Connection) -> None:
    migrate(conn)

    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(
            "INSERT INTO raw_notifications (user_id, remote_id, received_at, text) "
            "VALUES (?, ?, ?, ?)",
            (999, 1, "2026-11-18T10:00:00", "text"),
        )


def test_transaction_kind_is_checked(conn: sqlite3.Connection) -> None:
    migrate(conn)
    conn.execute(
        "INSERT INTO users (name, token, created_at) VALUES (?, ?, ?)",
        ("alice", "token", "2026-11-18T10:00:00"),
    )

    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(
            "INSERT INTO transactions (user_id, source, source_id, occurred_on, amount_minor, "
            "currency, kind, status) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (1, "csv", 1, "2026-11-18", -100, "PLN", "lottery", "settled"),
        )


def test_newer_database_is_rejected(conn: sqlite3.Connection) -> None:
    conn.execute("PRAGMA user_version = 999")

    with pytest.raises(PkoStatError, match="newer"):
        migrate(conn)
