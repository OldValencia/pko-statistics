import sqlite3
from pathlib import Path

from statement_data import CARD as CARD_ROW
from statement_data import PHONE_IN, write_statement

from pkostat.db.categories import set_override
from pkostat.db.notifications import insert_raw_notification
from pkostat.domain import Status
from pkostat.rebuild import rebuild
from pkostat.statement_import import import_statement
from pkostat.users import add_user

CARD = (
    "Payment card authorization\nAmount: 52,00 PLN.\n"
    "Place: WOLT, WARSAW.\nDate: 2026-11-18 19:12:09."
)
DEBIT = "Account debit\n-120,00 PLN Przelew na telefon - wysłany\n\nReceiver: JANE DOE"


def _store(conn: sqlite3.Connection, user_id: int, remote_id: int, text: str) -> None:
    with conn:
        insert_raw_notification(conn, user_id, remote_id, "2026-11-18T19:12:23", text)


def _transactions(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    return conn.execute(
        "SELECT user_id, source, occurred_at, amount_minor, kind, counterparty, location, status "
        "FROM transactions ORDER BY source_id"
    ).fetchall()


def test_rebuild_parses_and_counts_unrecognised(db: sqlite3.Connection) -> None:
    user = add_user(db, "alice")
    _store(db, user.id, 1, CARD)
    _store(db, user.id, 2, DEBIT)
    _store(db, user.id, 3, "BLIK code generated\n123")

    result = rebuild(db)

    assert result.pushes.total() == 2
    assert result.unparsed_headers == {"BLIK code generated": 1}
    rows = [tuple(row) for row in _transactions(db)]
    assert rows == [
        (
            user.id,
            "notification",
            "2026-11-18T19:12:09",
            -5200,
            "card",
            "WOLT",
            "WARSAW",
            "pending",
        ),
        (
            user.id,
            "notification",
            "2026-11-18T19:12:23",
            -12000,
            "transfer_out",
            "JANE DOE",
            None,
            "pending",
        ),
    ]


def test_rebuild_is_repeatable(db: sqlite3.Connection) -> None:
    user = add_user(db, "alice")
    _store(db, user.id, 1, CARD)

    rebuild(db)
    rebuild(db)

    assert len(_transactions(db)) == 1


def test_rebuild_one_user_leaves_others(db: sqlite3.Connection) -> None:
    alice = add_user(db, "alice")
    bob = add_user(db, "bob")
    _store(db, alice.id, 1, CARD)
    _store(db, bob.id, 2, CARD)
    rebuild(db)
    db.execute("DELETE FROM raw_notifications WHERE user_id = ?", (alice.id,))

    result = rebuild(db, alice.id)

    assert result.pushes.total() == 0
    assert [row["user_id"] for row in _transactions(db)] == [bob.id]


WOLT_PUSH = (
    "Payment card authorization\nAmount: 70,21 PLN.\n"
    "Place: WOLT, WARSAW.\nDate: 2026-11-10 20:01:02."
)


def test_statement_supersedes_matching_push(db: sqlite3.Connection, tmp_path: Path) -> None:
    user = add_user(db, "alice")
    _store(db, user.id, 1, WOLT_PUSH)
    _store(db, user.id, 2, CARD)  # 2026-11-18: after the statement, stays pending
    statement = write_statement(tmp_path / "x 01.11.2026 - 12.11.2026.csv", [CARD_ROW])
    import_statement(db, user, statement)

    result = rebuild(db)

    assert result.statement_rows == 1
    assert result.pushes == {Status.SUPERSEDED: 1, Status.PENDING: 1}
    rows = db.execute(
        "SELECT source, status, matched_csv_row_id FROM transactions ORDER BY source, source_id"
    ).fetchall()
    csv_id = db.execute("SELECT id FROM csv_rows").fetchone()[0]
    assert [tuple(row) for row in rows] == [
        ("csv", "settled", None),
        ("notification", "superseded", csv_id),
        ("notification", "pending", None),
    ]


def test_resent_push_counted_once(db: sqlite3.Connection) -> None:
    user = add_user(db, "alice")
    undated = "Payment card authorization\nAmount: 4,00 PLN.\nPlace: BUS, Gdansk."
    _store(db, user.id, 1, CARD)
    _store(db, user.id, 2, CARD + "\n")  # the Shortcut fired twice
    _store(db, user.id, 3, undated)
    _store(db, user.id, 4, undated)  # no timestamp: may be two real tickets, keep both

    result = rebuild(db)

    assert result.duplicate_pushes == 1
    assert result.pushes.total() == 3


HOLD_ROW = ["", "2026-11-10", "Blokada", "-70.21", "PLN", "W rozliczeniu", "Tytuł: P0002",
            "Lokalizacja: Adres: WOLT Miasto: WARSAW Kraj: POLSKA"]  # fmt: skip


def _statuses(conn: sqlite3.Connection) -> list[tuple[str, str]]:
    rows = conn.execute("SELECT source, status FROM transactions ORDER BY source, id").fetchall()
    return [(row["source"], row["status"]) for row in rows]


def test_hold_counts_and_supersedes_its_push(db: sqlite3.Connection, tmp_path: Path) -> None:
    user = add_user(db, "alice")
    _store(db, user.id, 1, WOLT_PUSH)
    import_statement(
        db, user, write_statement(tmp_path / "a 01.11.2026 - 12.11.2026.csv", [HOLD_ROW])
    )

    result = rebuild(db)

    assert result.holds == {Status.PENDING: 1}
    assert result.pushes == {Status.SUPERSEDED: 1}
    assert _statuses(db) == [("csv", "pending"), ("notification", "superseded")]


def test_booked_row_supersedes_hold_and_push(db: sqlite3.Connection, tmp_path: Path) -> None:
    user = add_user(db, "alice")
    _store(db, user.id, 1, WOLT_PUSH)
    import_statement(
        db, user, write_statement(tmp_path / "a 01.11.2026 - 12.11.2026.csv", [HOLD_ROW])
    )
    import_statement(
        db, user, write_statement(tmp_path / "b 01.11.2026 - 20.11.2026.csv", [CARD_ROW])
    )

    result = rebuild(db)

    assert result.holds == {Status.SUPERSEDED: 1}
    assert result.pushes == {Status.SUPERSEDED: 1}
    assert sorted(_statuses(db)) == [
        ("csv", "settled"),
        ("csv", "superseded"),
        ("notification", "superseded"),
    ]


def test_hold_never_booked_is_unmatched(db: sqlite3.Connection, tmp_path: Path) -> None:
    user = add_user(db, "alice")
    import_statement(
        db, user, write_statement(tmp_path / "a 01.11.2026 - 12.11.2026.csv", [HOLD_ROW])
    )
    import_statement(
        db, user, write_statement(tmp_path / "b 01.11.2026 - 30.11.2026.csv", [PHONE_IN])
    )

    result = rebuild(db)

    assert result.holds == {Status.UNMATCHED: 1}


def test_rebuild_assigns_merchant_keys_and_categories(db: sqlite3.Connection) -> None:
    user = add_user(db, "alice")
    _store(db, user.id, 1, CARD)
    _store(
        db, user.id, 2, "Payment card authorization\nAmount: 9,00 PLN.\nPlace: 820 KOMIS NOWAK, X."
    )

    result = rebuild(db)

    rows = db.execute("SELECT merchant_key, category FROM transactions ORDER BY id").fetchall()
    assert [tuple(row) for row in rows] == [("WOLT", "Food delivery"), ("KOMIS NOWAK", None)]
    assert (result.counted, result.uncategorised, result.uncategorised_minor) == (2, 1, -900)


def test_override_on_a_push_survives_the_statement(db: sqlite3.Connection, tmp_path: Path) -> None:
    user = add_user(db, "alice")
    _store(db, user.id, 1, WOLT_PUSH)  # 70,21 zł on 2026-11-10
    rebuild(db)
    with db:
        set_override(db, "notification", 1, "Groceries")  # it was Wolt Market
    first = write_statement(tmp_path / "a 01.11.2026 - 12.11.2026.csv", [HOLD_ROW])
    import_statement(db, user, first)
    rebuild(db)
    assert _counted_categories(db) == ["Groceries"]  # the hold took it over

    second = write_statement(tmp_path / "b 01.11.2026 - 20.11.2026.csv", [CARD_ROW])
    import_statement(db, user, second)
    rebuild(db)

    assert _counted_categories(db) == ["Groceries"]  # and the booked row from the hold


def _counted_categories(conn: sqlite3.Connection) -> list[str]:
    rows = conn.execute(
        "SELECT category FROM transactions WHERE status IN ('settled', 'pending')"
    ).fetchall()
    return [row["category"] for row in rows]
