import sqlite3
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class RawNotification:
    id: int
    user_id: int
    remote_id: int
    received_at: str
    text: str


def list_raw_notifications(
    conn: sqlite3.Connection, user_id: int | None = None
) -> list[RawNotification]:
    query = "SELECT id, user_id, remote_id, received_at, text FROM raw_notifications"
    params: tuple[int, ...] = ()
    if user_id is not None:
        query += " WHERE user_id = ?"
        params = (user_id,)
    rows = conn.execute(query + " ORDER BY id", params).fetchall()
    return [
        RawNotification(
            row["id"], row["user_id"], row["remote_id"], row["received_at"], row["text"]
        )
        for row in rows
    ]


def insert_raw_notification(
    conn: sqlite3.Connection, user_id: int, remote_id: int, received_at: str, text: str
) -> bool:
    """Store a notification; False if this remote_id is already stored."""
    cursor = conn.execute(
        "INSERT OR IGNORE INTO raw_notifications (user_id, remote_id, received_at, text) "
        "VALUES (?, ?, ?, ?)",
        (user_id, remote_id, received_at, text),
    )
    return cursor.rowcount == 1


def insert_rejected_notification(
    conn: sqlite3.Connection, remote_id: int, token_id: str, received_at: str, text: str
) -> bool:
    """Keep a notification with an unknown token; False if already kept."""
    cursor = conn.execute(
        "INSERT OR IGNORE INTO rejected_notifications (remote_id, token_id, received_at, text) "
        "VALUES (?, ?, ?, ?)",
        (remote_id, token_id, received_at, text),
    )
    return cursor.rowcount == 1


def notification_counts_by_user(conn: sqlite3.Connection) -> dict[int, int]:
    rows = conn.execute(
        "SELECT user_id, COUNT(*) AS total FROM raw_notifications GROUP BY user_id"
    ).fetchall()
    return {row["user_id"]: row["total"] for row in rows}
