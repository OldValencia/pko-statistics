"""Importing an iPKO CSV statement into csv_imports / csv_rows."""

import sqlite3
from dataclasses import dataclass
from pathlib import Path

from pkostat.clock import now_local_iso
from pkostat.db.statements import find_import_by_sha256, insert_csv_row, insert_import
from pkostat.db.users import User
from pkostat.errors import PkoStatError
from pkostat.ingest.statement.parser import parse_row
from pkostat.ingest.statement.reader import Statement, parse_statement, read_statement, row_key


@dataclass(frozen=True, slots=True)
class ImportResult:
    file_name: str
    period_from: str
    period_to: str
    new_rows: int
    known_rows: int
    pending_rows: int
    imported_before: str | None  # when the same file was imported earlier, if it was


def import_statement(conn: sqlite3.Connection, user: User, path: Path) -> ImportResult:
    return import_parsed(conn, user, read_statement(path))


def import_uploaded(
    conn: sqlite3.Connection, user: User, file_name: str, data: bytes
) -> ImportResult:
    return import_parsed(conn, user, parse_statement(file_name, data))


def import_parsed(conn: sqlite3.Connection, user: User, statement: Statement) -> ImportResult:
    """Store the statement's rows. Rows already stored (from this file imported earlier or from
    an overlapping statement) are recognised by content and skipped, so re-importing is safe."""
    earlier = find_import_by_sha256(conn, statement.sha256)
    if earlier is not None and earlier.user_id != user.id:
        raise PkoStatError(
            f"This file was already imported for another user ({earlier.file_name!r})."
        )
    # Parse everything before writing anything: a broken file must not be half-imported.
    for number, fields in enumerate(statement.rows, start=1):
        try:
            parse_row(fields)
        except PkoStatError as exc:
            raise PkoStatError(f"{statement.file_name}, row {number}: {exc}") from exc
    new_rows = 0
    with conn:
        if earlier is not None:
            import_id = earlier.id
        else:
            period = (statement.period_from, statement.period_to)
            import_id = insert_import(
                conn, user.id, statement.file_name, statement.sha256, period, now_local_iso()
            )
        for fields in statement.rows:
            new_rows += insert_csv_row(conn, import_id, user.id, row_key(fields), fields)
    return ImportResult(
        statement.file_name,
        statement.period_from,
        statement.period_to,
        new_rows,
        len(statement.rows) - new_rows,
        statement.pending_rows,
        None if earlier is None else earlier.imported_at,
    )
