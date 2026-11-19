"""merchant_rules (per-merchant category, manual or from the LLM) and transaction_overrides."""

import sqlite3
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class StoredRule:
    category: str
    source: str  # manual | llm


def stored_rules(conn: sqlite3.Connection) -> dict[str, StoredRule]:
    rows = conn.execute("SELECT merchant_key, category, source FROM merchant_rules").fetchall()
    return {row["merchant_key"]: StoredRule(row["category"], row["source"]) for row in rows}


def set_rule(
    conn: sqlite3.Connection, merchant_key: str, category: str, source: str, updated_at: str
) -> None:
    conn.execute(
        "INSERT INTO merchant_rules (merchant_key, category, source, updated_at) "
        "VALUES (?, ?, ?, ?) ON CONFLICT (merchant_key) DO UPDATE SET "
        "category = excluded.category, source = excluded.source, updated_at = excluded.updated_at",
        (merchant_key, category, source, updated_at),
    )


def delete_rule(conn: sqlite3.Connection, merchant_key: str) -> bool:
    cursor = conn.execute("DELETE FROM merchant_rules WHERE merchant_key = ?", (merchant_key,))
    return cursor.rowcount == 1


def overrides(conn: sqlite3.Connection) -> dict[tuple[str, int], str]:
    rows = conn.execute(
        "SELECT transaction_source, source_id, category FROM transaction_overrides"
    ).fetchall()
    return {(row["transaction_source"], row["source_id"]): row["category"] for row in rows}


def known_merchant_keys(conn: sqlite3.Connection) -> set[str]:
    rows = conn.execute(
        "SELECT DISTINCT merchant_key FROM transactions WHERE merchant_key IS NOT NULL"
    ).fetchall()
    return {row["merchant_key"] for row in rows}


def set_override(conn: sqlite3.Connection, source: str, source_id: int, category: str) -> None:
    conn.execute(
        "INSERT INTO transaction_overrides (transaction_source, source_id, category) "
        "VALUES (?, ?, ?) ON CONFLICT (transaction_source, source_id) "
        "DO UPDATE SET category = excluded.category",
        (source, source_id, category),
    )


def delete_override(conn: sqlite3.Connection, source: str, source_id: int) -> None:
    conn.execute(
        "DELETE FROM transaction_overrides WHERE transaction_source = ? AND source_id = ?",
        (source, source_id),
    )


def list_rules(conn: sqlite3.Connection) -> list[tuple[str, StoredRule]]:
    rows = conn.execute(
        "SELECT merchant_key, category, source FROM merchant_rules ORDER BY merchant_key"
    ).fetchall()
    return [(row["merchant_key"], StoredRule(row["category"], row["source"])) for row in rows]
