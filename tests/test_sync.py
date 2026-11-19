import sqlite3
from collections.abc import Sequence
from datetime import UTC, datetime

from pkostat.ingest.supabase import InboxRow
from pkostat.ingest.sync import sync_inbox
from pkostat.users import add_user

TOKEN = "00000000-1111-4222-8333-444444444444"


class FakeInbox:
    """In-memory stand-in for Supabase that also records what the DB held at delete time."""

    def __init__(self, conn: sqlite3.Connection, rows: list[InboxRow]) -> None:
        self.conn = conn
        self.rows = list(rows)
        self.stored_when_deleting: list[int] = []

    def fetch_after(self, after_id: int, limit: int) -> list[InboxRow]:
        return [row for row in self.rows if row.id > after_id][:limit]

    def delete(self, ids: Sequence[int]) -> None:
        self.stored_when_deleting.append(_stored_count(self.conn))
        self.rows = [row for row in self.rows if row.id not in ids]


def _row(remote_id: int, token: str = TOKEN, text: str = "Payment card authorization") -> InboxRow:
    created = datetime(2026, 7, 1, 21, 30, tzinfo=UTC)
    return InboxRow(id=remote_id, created_at=created, token_id=token, notification_text=text)


def _stored_count(conn: sqlite3.Connection) -> int:
    return conn.execute(
        "SELECT (SELECT COUNT(*) FROM raw_notifications) + "
        "(SELECT COUNT(*) FROM rejected_notifications)"
    ).fetchone()[0]


def test_stores_known_and_rejects_unknown_tokens(db: sqlite3.Connection) -> None:
    add_user(db, "alice", TOKEN)
    inbox = FakeInbox(db, [_row(1), _row(2, token="unknown-token-123456"), _row(3)])

    result = sync_inbox(db, inbox)

    assert (result.stored, result.rejected, result.duplicates) == (2, 1, 0)
    assert inbox.rows == []
    rejected = db.execute("SELECT remote_id, token_id FROM rejected_notifications").fetchone()
    assert tuple(rejected) == (2, "unknown-token-123456")


def test_received_at_is_warsaw_time(db: sqlite3.Connection) -> None:
    add_user(db, "alice", TOKEN)

    sync_inbox(db, FakeInbox(db, [_row(1)]))

    # 21:30 UTC in July is 23:30 in Warsaw (CEST, UTC+2).
    received_at = db.execute("SELECT received_at FROM raw_notifications").fetchone()[0]
    assert received_at == "2026-07-01T23:30:00"


def test_identical_texts_are_separate_notifications(db: sqlite3.Connection) -> None:
    add_user(db, "alice", TOKEN)

    result = sync_inbox(db, FakeInbox(db, [_row(1, text="same"), _row(2, text="same")]))

    assert result.stored == 2


def test_already_stored_rows_are_skipped_and_deleted(db: sqlite3.Connection) -> None:
    add_user(db, "alice", TOKEN)
    sync_inbox(db, FakeInbox(db, [_row(1)]))
    # Simulates a crash after COMMIT but before DELETE: the row is still in Supabase.
    inbox = FakeInbox(db, [_row(1), _row(2)])

    result = sync_inbox(db, inbox)

    assert (result.stored, result.duplicates) == (1, 1)
    assert inbox.rows == []


def test_paginates_and_deletes_only_after_commit(db: sqlite3.Connection) -> None:
    add_user(db, "alice", TOKEN)
    inbox = FakeInbox(db, [_row(i) for i in range(1, 6)])

    result = sync_inbox(db, inbox, page_size=2)

    assert result.stored == 5
    assert inbox.stored_when_deleting == [2, 4, 5]


def test_empty_inbox(db: sqlite3.Connection) -> None:
    inbox = FakeInbox(db, [])

    result = sync_inbox(db, inbox)

    assert (result.stored, result.rejected, result.duplicates) == (0, 0, 0)
    assert inbox.stored_when_deleting == []
