"""`pkostat publish`: render each shared user's report, lock it, push the site if anything changed.

The last published state is remembered as a digest of the plain reports and passwords, so a
scheduled run every couple of hours pushes only when there is something new.
"""

import hashlib
import json
import sqlite3
from dataclasses import dataclass
from pathlib import Path

from pkostat.clock import now_local_iso
from pkostat.config import Settings
from pkostat.db.users import list_users
from pkostat.errors import PkoStatError
from pkostat.publish.git import push_site
from pkostat.publish.site import Page, build_site, locked_template
from pkostat.report.render import render_report
from pkostat.report_service import report_data_for

STATE_FILE = "publish-state.json"


@dataclass(frozen=True, slots=True)
class PublishResult:
    changed: bool
    reports: int
    published_at: str | None


def publish_reports(
    conn: sqlite3.Connection, settings: Settings, force: bool = False
) -> PublishResult:
    if not settings.publish_remote:
        raise PkoStatError("Publishing is off: set PKOSTAT_PUBLISH_REMOTE in .env.")
    pages = [
        Page(
            user.share_id,
            user.share_password,
            render_report(report_data_for(conn, settings, user), "user"),
        )
        for user in list_users(conn)
        if user.share_id and user.share_password
    ]
    digest = _digest(pages)
    state = last_publish(settings)
    if not force and state.get("digest") == digest:
        return PublishResult(False, len(pages), state.get("published_at"))
    push_site(build_site(pages), settings.publish_remote)
    published_at = now_local_iso()
    _state_path(settings).write_text(
        json.dumps({"digest": digest, "published_at": published_at}), encoding="utf-8"
    )
    return PublishResult(True, len(pages), published_at)


def last_publish(settings: Settings) -> dict[str, str]:
    path = _state_path(settings)
    try:
        state = json.loads(path.read_text(encoding="utf-8"))
    except OSError, ValueError:
        return {}
    return state if isinstance(state, dict) else {}


def _digest(pages: list[Page]) -> str:
    hasher = hashlib.sha256(locked_template().encode("utf-8"))
    for page in sorted(pages, key=lambda p: p.share_id):
        for part in (page.share_id, page.password, page.html):
            raw = part.encode("utf-8")
            hasher.update(len(raw).to_bytes(8, "big") + raw)
    return hasher.hexdigest()


def _state_path(settings: Settings) -> Path:
    return settings.home / STATE_FILE
