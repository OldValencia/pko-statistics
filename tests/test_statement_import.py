import sqlite3
from pathlib import Path

import pytest
from statement_data import BILL, CARD, PENDING, PHONE_IN, PHONE_OUT, write_statement

from pkostat.db.statements import covered_until
from pkostat.errors import PkoStatError
from pkostat.statement_import import import_statement
from pkostat.users import add_user


def _rows(conn: sqlite3.Connection) -> int:
    return conn.execute("SELECT COUNT(*) FROM csv_rows").fetchone()[0]


def test_import_stores_all_rows_including_holds(db: sqlite3.Connection, tmp_path: Path) -> None:
    user = add_user(db, "alice")
    path = write_statement(tmp_path / "a 01.11.2026 - 12.11.2026.csv", [PENDING, CARD, PHONE_IN])

    result = import_statement(db, user, path)

    assert (result.new_rows, result.known_rows, result.pending_rows) == (3, 0, 1)
    assert result.imported_before is None
    assert _rows(db) == 3
    assert covered_until(db, user.id) == "2026-11-12"


def test_same_file_again_adds_nothing(db: sqlite3.Connection, tmp_path: Path) -> None:
    user = add_user(db, "alice")
    path = write_statement(tmp_path / "a.csv", [CARD, PENDING])
    import_statement(db, user, path)

    result = import_statement(db, user, path)

    assert (result.new_rows, result.known_rows) == (0, 2)
    assert result.imported_before is not None
    assert db.execute("SELECT COUNT(*) FROM csv_imports").fetchone()[0] == 1


def test_same_file_for_another_user_is_refused(db: sqlite3.Connection, tmp_path: Path) -> None:
    path = write_statement(tmp_path / "a.csv", [CARD])
    import_statement(db, add_user(db, "alice"), path)

    with pytest.raises(PkoStatError, match="another user"):
        import_statement(db, add_user(db, "bob"), path)


def test_overlapping_statements_do_not_duplicate(db: sqlite3.Connection, tmp_path: Path) -> None:
    user = add_user(db, "alice")
    import_statement(db, user, write_statement(tmp_path / "old.csv", [BILL, PHONE_OUT, PENDING]))

    result = import_statement(
        db, user, write_statement(tmp_path / "new.csv", [PENDING, PHONE_OUT, CARD])
    )

    assert (result.new_rows, result.known_rows) == (1, 2)
    assert _rows(db) == 4


def test_broken_row_imports_nothing(db: sqlite3.Connection, tmp_path: Path) -> None:
    user = add_user(db, "alice")
    broken = [*CARD[:3], "a lot", *CARD[4:]]
    path = write_statement(tmp_path / "a.csv", [CARD, broken])

    with pytest.raises(PkoStatError, match="row 2"):
        import_statement(db, user, path)

    assert _rows(db) == 0
    assert db.execute("SELECT COUNT(*) FROM csv_imports").fetchone()[0] == 0
