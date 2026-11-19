"""Moving notifications from the Supabase inbox into the local database."""

import logging
import sqlite3
from dataclasses import dataclass
from enum import StrEnum

from pkostat.clock import to_local_iso
from pkostat.db.notifications import insert_raw_notification, insert_rejected_notification
from pkostat.db.users import user_ids_by_token
from pkostat.ingest.supabase import Inbox, InboxRow

log = logging.getLogger(__name__)

PAGE_SIZE = 500


class Outcome(StrEnum):
    STORED = "stored"
    REJECTED = "rejected"
    DUPLICATE = "duplicate"


@dataclass(frozen=True, slots=True)
class SyncResult:
    stored: int
    rejected: int
    duplicates: int


def sync_inbox(conn: sqlite3.Connection, inbox: Inbox, page_size: int = PAGE_SIZE) -> SyncResult:
    owners = user_ids_by_token(conn)
    counts = dict.fromkeys(Outcome, 0)
    after_id = 0
    while page := inbox.fetch_after(after_id, page_size):
        with conn:
            for row in page:
                counts[_store(conn, owners, row)] += 1
        # Delete only after COMMIT: if we crash in between, the rows stay in Supabase and the
        # next sync skips them by remote_id. Nothing is lost either way.
        inbox.delete([row.id for row in page])
        log.debug("Synced page of %d ending at id %d", len(page), page[-1].id)
        after_id = page[-1].id
        if len(page) < page_size:
            break
    return SyncResult(counts[Outcome.STORED], counts[Outcome.REJECTED], counts[Outcome.DUPLICATE])


def _store(conn: sqlite3.Connection, owners: dict[str, int], row: InboxRow) -> Outcome:
    received_at = to_local_iso(row.created_at)
    user_id = owners.get(row.token_id)
    if user_id is None:
        inserted = insert_rejected_notification(
            conn, row.id, row.token_id, received_at, row.notification_text
        )
        return Outcome.REJECTED if inserted else Outcome.DUPLICATE
    inserted = insert_raw_notification(conn, user_id, row.id, received_at, row.notification_text)
    return Outcome.STORED if inserted else Outcome.DUPLICATE
