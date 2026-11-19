import sqlite3

import pytest

from pkostat.db.users import find_user_by_name, list_users
from pkostat.errors import PkoStatError
from pkostat.users import add_user, rotate_token, set_display_name

UUID_TOKEN = "00000000-1111-4222-8333-444444444444"


def test_add_generates_token(db: sqlite3.Connection) -> None:
    user = add_user(db, "alice")

    assert len(user.token) >= 16
    assert find_user_by_name(db, "alice") == user


def test_add_with_existing_uuid_token(db: sqlite3.Connection) -> None:
    user = add_user(db, "alice", UUID_TOKEN)

    assert user.token == UUID_TOKEN


def test_generated_tokens_differ(db: sqlite3.Connection) -> None:
    assert add_user(db, "alice").token != add_user(db, "bob").token


@pytest.mark.parametrize("name", ["", "Alice", "with space", "-dash", "x" * 33])
def test_invalid_names_rejected(db: sqlite3.Connection, name: str) -> None:
    with pytest.raises(PkoStatError, match="Invalid user name"):
        add_user(db, name)


@pytest.mark.parametrize("token", ["short", "has space in it 1234", 'quote"quote"quote"'])
def test_invalid_tokens_rejected(db: sqlite3.Connection, token: str) -> None:
    with pytest.raises(PkoStatError, match="Invalid token"):
        add_user(db, "alice", token)


def test_duplicate_name_rejected(db: sqlite3.Connection) -> None:
    add_user(db, "alice")

    with pytest.raises(PkoStatError, match="already exists"):
        add_user(db, "alice")


def test_duplicate_token_rejected(db: sqlite3.Connection) -> None:
    add_user(db, "alice", UUID_TOKEN)

    with pytest.raises(PkoStatError, match="belongs to user 'alice'"):
        add_user(db, "bob", UUID_TOKEN)


def test_rotate_replaces_token(db: sqlite3.Connection) -> None:
    old = add_user(db, "alice", UUID_TOKEN)

    new = rotate_token(db, "alice")

    assert new.token != old.token
    assert find_user_by_name(db, "alice") == new


def test_rotate_unknown_user(db: sqlite3.Connection) -> None:
    with pytest.raises(PkoStatError, match="No user 'ghost'"):
        rotate_token(db, "ghost")


def test_list_sorted_by_name(db: sqlite3.Connection) -> None:
    add_user(db, "bob")
    add_user(db, "alice")

    assert [user.name for user in list_users(db)] == ["alice", "bob"]


def test_display_name_is_cleaned(db: sqlite3.Connection) -> None:
    user = add_user(db, "jane", display_name="  Jane   Doe ")

    assert user.display_name == "Jane Doe"
    assert user.label == "Jane Doe"


def test_label_falls_back_to_name(db: sqlite3.Connection) -> None:
    assert add_user(db, "alice").label == "alice"


def test_set_and_clear_display_name(db: sqlite3.Connection) -> None:
    add_user(db, "alice")

    assert set_display_name(db, "alice", "Alice Smith").label == "Alice Smith"
    assert find_user_by_name(db, "alice").display_name == "Alice Smith"
    assert set_display_name(db, "alice", "").display_name is None


@pytest.mark.parametrize("display_name", ["x" * 65, "tab\u0007bell"])
def test_invalid_display_name(db: sqlite3.Connection, display_name: str) -> None:
    with pytest.raises(PkoStatError, match="Invalid display name"):
        add_user(db, "alice", display_name=display_name)
