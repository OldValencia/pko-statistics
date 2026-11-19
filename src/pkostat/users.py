"""Users and their tokens. A token is the routing tag the iOS Shortcut sends as token_id."""

import re
import secrets
import sqlite3
from dataclasses import replace

from pkostat.clock import now_local_iso
from pkostat.db.users import (
    User,
    find_user_by_name,
    find_user_by_token,
    insert_user,
    update_display_name,
    update_token,
)
from pkostat.errors import PkoStatError

MAX_DISPLAY_NAME = 64

_NAME = re.compile(r"^[a-z0-9][a-z0-9_-]{0,31}$")
# Generated tokens and UUIDs both fit; whitespace or quotes would break the Shortcut's JSON.
_TOKEN = re.compile(r"^[A-Za-z0-9_-]{16,99}$")


def generate_token() -> str:
    return secrets.token_urlsafe(24)


def add_user(
    conn: sqlite3.Connection,
    name: str,
    token: str | None = None,
    display_name: str | None = None,
) -> User:
    _check_name(name)
    token = generate_token() if token is None else token
    _check_token(token)
    display_name = _clean_display_name(display_name)
    if find_user_by_name(conn, name) is not None:
        raise PkoStatError(f"User '{name}' already exists.")
    _check_token_free(conn, token)
    with conn:
        return insert_user(conn, name, token, now_local_iso(), display_name)


def rotate_token(conn: sqlite3.Connection, name: str) -> User:
    user = get_user(conn, name)
    token = generate_token()
    with conn:
        update_token(conn, user.id, token)
    return replace(user, token=token)


def set_display_name(conn: sqlite3.Connection, name: str, display_name: str | None) -> User:
    """Set the name shown in reports; None or blank clears it back to the user name."""
    user = get_user(conn, name)
    display_name = _clean_display_name(display_name)
    with conn:
        update_display_name(conn, user.id, display_name)
    return replace(user, display_name=display_name)


def get_user(conn: sqlite3.Connection, name: str) -> User:
    user = find_user_by_name(conn, name)
    if user is None:
        raise PkoStatError(f"No user '{name}'. See `pkostat user list`.")
    return user


def _check_name(name: str) -> None:
    if not _NAME.match(name):
        raise PkoStatError(
            f"Invalid user name '{name}': use 1-32 lowercase letters, digits, '-' or '_'."
        )


def _clean_display_name(display_name: str | None) -> str | None:
    if display_name is None:
        return None
    cleaned = " ".join(display_name.split())
    if not cleaned:
        return None
    if len(cleaned) > MAX_DISPLAY_NAME or not cleaned.isprintable():
        raise PkoStatError(f"Invalid display name: up to {MAX_DISPLAY_NAME} printable characters.")
    return cleaned


def _check_token(token: str) -> None:
    if not _TOKEN.match(token):
        raise PkoStatError("Invalid token: use 16-99 characters from A-Z, a-z, 0-9, '-' and '_'.")


def _check_token_free(conn: sqlite3.Connection, token: str) -> None:
    owner = find_user_by_token(conn, token)
    if owner is not None:
        raise PkoStatError(f"This token already belongs to user '{owner.name}'.")
