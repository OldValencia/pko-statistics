"""Rebuilding the derived transactions table from raw input, reconciled per user.

Precedence for one real operation: a settled statement row beats a statement hold ('Blokada'),
which beats a push. Lower-ranked copies are marked superseded and drop out of statistics.
Merchant keys are set before reconciliation (it compares merchants), categories after.
Safe to run any time; raw input is never touched."""

import sqlite3
from collections import Counter
from dataclasses import dataclass, field

from pkostat.categorize.categorizer import Categorizer
from pkostat.categorize.config import CategoryConfig, load_category_config
from pkostat.db.categories import overrides, stored_rules
from pkostat.db.notifications import RawNotification, list_raw_notifications
from pkostat.db.statements import RawCsvRow, covered_until, list_csv_rows
from pkostat.db.transactions import delete_transactions, insert_transaction
from pkostat.db.users import list_users
from pkostat.domain import Source, Status, Transaction
from pkostat.errors import PkoStatError
from pkostat.ingest.notifications import duplicate_key, notification_header, parse_notification
from pkostat.ingest.statement.parser import parse_row
from pkostat.reconcile import reconcile


@dataclass(slots=True)
class RebuildResult:
    statement_rows: int = 0
    statement_errors: int = 0
    holds: Counter[Status] = field(default_factory=Counter)
    duplicate_pushes: int = 0
    pushes: Counter[Status] = field(default_factory=Counter)
    unparsed_headers: Counter[str] = field(default_factory=Counter)
    counted: int = 0
    uncategorised: int = 0
    uncategorised_minor: int = 0

    @property
    def unparsed(self) -> int:
        return self.unparsed_headers.total()


def rebuild(
    conn: sqlite3.Connection, user_id: int | None = None, config: CategoryConfig | None = None
) -> RebuildResult:
    """Replace the user's transactions (all users when None) in one database transaction.
    Without a config the packaged default categories and rules are used."""
    user_ids = [user_id] if user_id is not None else [user.id for user in list_users(conn)]
    categorizer = Categorizer(config or load_category_config(), stored_rules(conn), overrides(conn))
    result = RebuildResult()
    with conn:
        delete_transactions(conn, user_id)
        for uid in user_ids:
            last_day = covered_until(conn, uid)
            statement = [
                categorizer.with_merchant_key(tx)
                for tx in _statement_transactions(conn, uid, result)
            ]
            settled = [tx for tx in statement if tx.status == Status.SETTLED]
            holds = reconcile(
                [tx for tx in statement if tx.status != Status.SETTLED], settled, last_day
            )
            live_holds = [tx for tx in holds if tx.status == Status.PENDING]
            pushes = reconcile(
                [categorizer.with_merchant_key(tx) for tx in _push_transactions(conn, uid, result)],
                settled + live_holds,
                last_day,
            )
            result.holds.update(tx.status for tx in holds)
            result.pushes.update(tx.status for tx in pushes)
            # Pushes first: a push can be matched to a hold, which in turn is matched to a row.
            for replaced in [*pushes, *holds]:
                if replaced.status == Status.SUPERSEDED:
                    categorizer.inherit_override(replaced)
            for tx in [*settled, *holds, *pushes]:
                tx = categorizer.with_category(tx)
                _count_category(result, tx)
                insert_transaction(conn, tx)
    return result


def _count_category(result: RebuildResult, tx: Transaction) -> None:
    if not tx.counted:
        return
    result.counted += 1
    if tx.category is None:
        result.uncategorised += 1
        result.uncategorised_minor += tx.amount_minor


def _statement_transactions(
    conn: sqlite3.Connection, user_id: int, result: RebuildResult
) -> list[Transaction]:
    transactions: list[Transaction] = []
    for raw in list_csv_rows(conn, user_id):
        tx = _from_csv_row(raw)
        if tx is None:
            result.statement_errors += 1
            continue
        transactions.append(tx)
    result.statement_rows += len(transactions)
    return transactions


def _push_transactions(
    conn: sqlite3.Connection, user_id: int, result: RebuildResult
) -> list[Transaction]:
    transactions: list[Transaction] = []
    seen: set[str] = set()
    for raw in list_raw_notifications(conn, user_id):
        key = duplicate_key(raw.text)
        if key is not None:
            if key in seen:
                result.duplicate_pushes += 1
                continue
            seen.add(key)
        tx = _from_notification(raw)
        if tx is None:
            result.unparsed_headers[notification_header(raw.text) or "(empty)"] += 1
            continue
        transactions.append(tx)
    return transactions


def _from_csv_row(raw: RawCsvRow) -> Transaction | None:
    # Rows were validated on import; an error here means the parser changed since then.
    try:
        entry = parse_row(raw.fields)
    except PkoStatError:
        return None
    return Transaction(
        user_id=raw.user_id,
        source=Source.CSV,
        source_id=raw.id,
        occurred_on=entry.occurred_on,
        occurred_at=entry.occurred_at,
        amount_minor=entry.amount_minor,
        currency=entry.currency,
        kind=entry.kind,
        counterparty=entry.counterparty,
        location=entry.location,
        title=entry.title,
        status=Status.PENDING if entry.pending else Status.SETTLED,
    )


def _from_notification(raw: RawNotification) -> Transaction | None:
    parsed = parse_notification(raw.text, raw.received_at)
    if parsed is None:
        return None
    return Transaction(
        user_id=raw.user_id,
        source=Source.NOTIFICATION,
        source_id=raw.id,
        occurred_on=parsed.occurred_on,
        occurred_at=parsed.occurred_at,
        amount_minor=parsed.amount_minor,
        currency=parsed.currency,
        kind=parsed.kind,
        counterparty=parsed.counterparty,
        location=parsed.location,
        title=parsed.title,
        status=Status.PENDING,  # final status is set by reconcile()
    )
