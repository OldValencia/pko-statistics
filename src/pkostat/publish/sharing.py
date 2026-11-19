"""Which users' reports are published, under which secret path and password."""

import secrets
import sqlite3
from dataclasses import replace

from pkostat.config import Settings
from pkostat.db.users import User, update_share
from pkostat.users import get_user


def open_share(conn: sqlite3.Connection, name: str) -> User:
    """Publish the user's report under a new path and password; the old link stops working."""
    user = get_user(conn, name)
    share_id, password = secrets.token_urlsafe(16), secrets.token_urlsafe(16)
    with conn:
        update_share(conn, user.id, share_id, password)
    return replace(user, share_id=share_id, share_password=password)


def close_share(conn: sqlite3.Connection, name: str) -> User:
    user = get_user(conn, name)
    with conn:
        update_share(conn, user.id, None, None)
    return replace(user, share_id=None, share_password=None)


def share_link(settings: Settings, user: User) -> str | None:
    """The link to send: the password rides in the fragment, which browsers never send to the
    server; the page reads it, remembers it on the device and removes it from the address bar."""
    site = site_url(settings)
    if site is None or not user.share_id or not user.share_password:
        return None
    return f"{site}/{user.share_id}/#k={user.share_password}"


def site_url(settings: Settings) -> str | None:
    if settings.publish_url:
        return settings.publish_url.rstrip("/")
    remote = settings.publish_remote or ""
    for prefix in ("git@github.com:", "https://github.com/", "ssh://git@github.com/"):
        if remote.startswith(prefix):
            owner, _, repo = remote.removeprefix(prefix).removesuffix(".git").partition("/")
            if not owner or not repo or "/" in repo:
                return None
            host = f"https://{owner.lower()}.github.io"
            return host if repo.lower() == f"{owner.lower()}.github.io" else f"{host}/{repo}"
    return None
