import sqlite3
from dataclasses import dataclass

_SELECT = "SELECT id, name, token, created_at, display_name, share_id, share_password FROM users"


@dataclass(frozen=True, slots=True)
class User:
    id: int
    name: str
    token: str
    created_at: str
    display_name: str | None = None
    share_id: str | None = None  # secret path of the published report; None = not published
    share_password: str | None = None  # encrypts the published report

    @property
    def label(self) -> str:
        return self.display_name or self.name


def insert_user(
    conn: sqlite3.Connection, name: str, token: str, created_at: str, display_name: str | None
) -> User:
    cursor = conn.execute(
        "INSERT INTO users (name, token, created_at, display_name) VALUES (?, ?, ?, ?)",
        (name, token, created_at, display_name),
    )
    assert cursor.lastrowid is not None
    return User(cursor.lastrowid, name, token, created_at, display_name)


def find_user_by_name(conn: sqlite3.Connection, name: str) -> User | None:
    row = conn.execute(_SELECT + " WHERE name = ?", (name,)).fetchone()
    return None if row is None else _to_user(row)


def find_user_by_token(conn: sqlite3.Connection, token: str) -> User | None:
    row = conn.execute(_SELECT + " WHERE token = ?", (token,)).fetchone()
    return None if row is None else _to_user(row)


def list_users(conn: sqlite3.Connection) -> list[User]:
    rows = conn.execute(_SELECT + " ORDER BY name").fetchall()
    return [_to_user(row) for row in rows]


def update_token(conn: sqlite3.Connection, user_id: int, token: str) -> None:
    conn.execute("UPDATE users SET token = ? WHERE id = ?", (token, user_id))


def update_display_name(conn: sqlite3.Connection, user_id: int, display_name: str | None) -> None:
    conn.execute("UPDATE users SET display_name = ? WHERE id = ?", (display_name, user_id))


def update_share(
    conn: sqlite3.Connection, user_id: int, share_id: str | None, password: str | None
) -> None:
    conn.execute(
        "UPDATE users SET share_id = ?, share_password = ? WHERE id = ?",
        (share_id, password, user_id),
    )


def user_ids_by_token(conn: sqlite3.Connection) -> dict[str, int]:
    rows = conn.execute("SELECT token, id FROM users").fetchall()
    return {row["token"]: row["id"] for row in rows}


def _to_user(row: sqlite3.Row) -> User:
    return User(
        row["id"],
        row["name"],
        row["token"],
        row["created_at"],
        row["display_name"],
        row["share_id"],
        row["share_password"],
    )
