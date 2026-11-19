import sqlite3
from dataclasses import dataclass

from pkostat.domain import Kind, Source, Status, Transaction


@dataclass(frozen=True, slots=True)
class UncategorisedMerchant:
    merchant_key: str | None
    example: str | None  # one counterparty spelling
    count: int
    total_minor: int


def delete_transactions(conn: sqlite3.Connection, user_id: int | None) -> None:
    if user_id is None:
        conn.execute("DELETE FROM transactions")
    else:
        conn.execute("DELETE FROM transactions WHERE user_id = ?", (user_id,))


def insert_transaction(conn: sqlite3.Connection, tx: Transaction) -> None:
    conn.execute(
        "INSERT INTO transactions (user_id, source, source_id, occurred_on, occurred_at, "
        "amount_minor, currency, kind, counterparty, location, merchant_key, title, status, "
        "matched_csv_row_id, category) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (
            tx.user_id,
            tx.source,
            tx.source_id,
            tx.occurred_on,
            tx.occurred_at,
            tx.amount_minor,
            tx.currency,
            tx.kind,
            tx.counterparty,
            tx.location,
            tx.merchant_key,
            tx.title,
            tx.status,
            tx.matched_csv_row_id,
            tx.category,
        ),
    )


def list_transactions(conn: sqlite3.Connection, user_id: int) -> list[Transaction]:
    rows = conn.execute(
        "SELECT user_id, source, source_id, occurred_on, occurred_at, amount_minor, currency, "
        "kind, counterparty, location, title, status, merchant_key, matched_csv_row_id, category "
        "FROM transactions WHERE user_id = ? ORDER BY occurred_on, id",
        (user_id,),
    ).fetchall()
    return [
        Transaction(
            user_id=row["user_id"],
            source=Source(row["source"]),
            source_id=row["source_id"],
            occurred_on=row["occurred_on"],
            occurred_at=row["occurred_at"],
            amount_minor=row["amount_minor"],
            currency=row["currency"],
            kind=Kind(row["kind"]),
            counterparty=row["counterparty"],
            location=row["location"],
            title=row["title"],
            status=Status(row["status"]),
            merchant_key=row["merchant_key"],
            matched_csv_row_id=row["matched_csv_row_id"],
            category=row["category"],
        )
        for row in rows
    ]


def uncategorised_merchants(
    conn: sqlite3.Connection, user_id: int | None, limit: int
) -> list[UncategorisedMerchant]:
    """Merchants of counted transactions without a category, biggest money first."""
    query = (
        "SELECT merchant_key, MIN(counterparty) AS example, COUNT(*) AS count, "
        "SUM(amount_minor) AS total FROM transactions "
        "WHERE category IS NULL AND status IN ('settled', 'pending')"
    )
    params: list[int] = []
    if user_id is not None:
        query += " AND user_id = ?"
        params.append(user_id)
    query += " GROUP BY merchant_key ORDER BY ABS(SUM(amount_minor)) DESC LIMIT ?"
    params.append(limit)
    rows = conn.execute(query, params).fetchall()
    return [
        UncategorisedMerchant(row["merchant_key"], row["example"], row["count"], row["total"])
        for row in rows
    ]


def category_usage(conn: sqlite3.Connection) -> dict[str, int]:
    rows = conn.execute(
        "SELECT category, COUNT(*) AS n FROM transactions "
        "WHERE category IS NOT NULL GROUP BY category"
    ).fetchall()
    return {row["category"]: row["n"] for row in rows}


def status_counts(conn: sqlite3.Connection) -> dict[str, int]:
    rows = conn.execute("SELECT status, COUNT(*) AS n FROM transactions GROUP BY status").fetchall()
    return {row["status"]: row["n"] for row in rows}


def unparsed_notifications(conn: sqlite3.Connection) -> int:
    """Raw pushes no parser turned into a transaction."""
    return conn.execute(
        "SELECT COUNT(*) FROM raw_notifications r WHERE NOT EXISTS (SELECT 1 FROM transactions t "
        "WHERE t.source = 'notification' AND t.source_id = r.id)"
    ).fetchone()[0]
