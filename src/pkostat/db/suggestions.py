import sqlite3
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Suggestion:
    merchant_key: str
    category: str
    confidence: float


def save_suggestions(
    conn: sqlite3.Connection, suggestions: list[Suggestion], model: str, created_at: str
) -> None:
    conn.executemany(
        "INSERT INTO llm_suggestions (merchant_key, category, confidence, model, created_at) "
        "VALUES (?, ?, ?, ?, ?) ON CONFLICT (merchant_key) DO UPDATE SET "
        "category = excluded.category, confidence = excluded.confidence, "
        "model = excluded.model, created_at = excluded.created_at",
        [(s.merchant_key, s.category, s.confidence, model, created_at) for s in suggestions],
    )


def list_suggestions(conn: sqlite3.Connection) -> dict[str, Suggestion]:
    rows = conn.execute("SELECT merchant_key, category, confidence FROM llm_suggestions").fetchall()
    return {
        row["merchant_key"]: Suggestion(row["merchant_key"], row["category"], row["confidence"])
        for row in rows
    }
