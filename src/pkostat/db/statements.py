import json
import sqlite3
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class StatementImport:
    id: int
    user_id: int
    file_name: str
    imported_at: str


@dataclass(frozen=True, slots=True)
class RawCsvRow:
    id: int
    user_id: int
    fields: tuple[str, ...]


def find_import_by_sha256(conn: sqlite3.Connection, sha256: str) -> StatementImport | None:
    row = conn.execute(
        "SELECT id, user_id, file_name, imported_at FROM csv_imports WHERE file_sha256 = ?",
        (sha256,),
    ).fetchone()
    if row is None:
        return None
    return StatementImport(row["id"], row["user_id"], row["file_name"], row["imported_at"])


def insert_import(
    conn: sqlite3.Connection,
    user_id: int,
    file_name: str,
    sha256: str,
    period: tuple[str, str],
    imported_at: str,
) -> int:
    cursor = conn.execute(
        "INSERT INTO csv_imports (user_id, file_name, file_sha256, period_from, period_to, "
        "imported_at) VALUES (?, ?, ?, ?, ?, ?)",
        (user_id, file_name, sha256, period[0], period[1], imported_at),
    )
    assert cursor.lastrowid is not None
    return cursor.lastrowid


def insert_csv_row(
    conn: sqlite3.Connection, import_id: int, user_id: int, key: str, fields: tuple[str, ...]
) -> bool:
    """Store a statement row; False if an earlier (overlapping) statement already had it."""
    cursor = conn.execute(
        "INSERT OR IGNORE INTO csv_rows (import_id, user_id, row_key, raw_json) "
        "VALUES (?, ?, ?, ?)",
        (import_id, user_id, key, json.dumps(fields, ensure_ascii=False)),
    )
    return cursor.rowcount == 1


def list_csv_rows(conn: sqlite3.Connection, user_id: int) -> list[RawCsvRow]:
    rows = conn.execute(
        "SELECT id, user_id, raw_json FROM csv_rows WHERE user_id = ? ORDER BY id", (user_id,)
    ).fetchall()
    return [
        RawCsvRow(row["id"], row["user_id"], tuple(json.loads(row["raw_json"]))) for row in rows
    ]


def covered_until(conn: sqlite3.Connection, user_id: int) -> str | None:
    """Last day covered by any imported statement of the user."""
    row = conn.execute(
        "SELECT MAX(period_to) AS last_day FROM csv_imports WHERE user_id = ?", (user_id,)
    ).fetchone()
    return row["last_day"]


def covered_from(conn: sqlite3.Connection, user_id: int) -> str | None:
    """First day covered by any imported statement of the user."""
    row = conn.execute(
        "SELECT MIN(period_from) AS first_day FROM csv_imports WHERE user_id = ?", (user_id,)
    ).fetchone()
    return row["first_day"]


@dataclass(frozen=True, slots=True)
class ImportInfo:
    user_name: str
    file_name: str
    period_from: str
    period_to: str
    imported_at: str
    rows: int


def list_imports(conn: sqlite3.Connection) -> list[ImportInfo]:
    rows = conn.execute(
        "SELECT u.name, i.file_name, i.period_from, i.period_to, i.imported_at, "
        "(SELECT COUNT(*) FROM csv_rows r WHERE r.import_id = i.id) AS row_count "
        "FROM csv_imports i JOIN users u ON u.id = i.user_id ORDER BY i.imported_at DESC"
    ).fetchall()
    return [
        ImportInfo(
            r["name"],
            r["file_name"],
            r["period_from"],
            r["period_to"],
            r["imported_at"],
            r["row_count"],
        )
        for r in rows
    ]
