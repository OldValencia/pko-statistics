"""Suggesting categories for merchants no rule knows. Suggestions only: the owner confirms them on
the Uncategorised page. A blind test on 135 known merchants: 64 % right, and one confident answer
in five wrong — far too many to write into the data unseen."""

import collections
import json
import sqlite3
import statistics
from collections import defaultdict
from dataclasses import dataclass
from typing import Literal

from pydantic import BaseModel, Field, create_model

from pkostat.categorize.config import CategoryConfig
from pkostat.clock import now_local_iso
from pkostat.db.suggestions import Suggestion, save_suggestions
from pkostat.llm.ollama import ChatModel, prompt

BATCH = 25
CONFIDENT = 0.6  # below this the page shows the suggestion without pre-selecting it
EXAMPLES = 60
SPEND_KINDS = ("essential", "discretionary", "impulse", "other")


@dataclass(frozen=True, slots=True)
class SuggestResult:
    asked: int
    confident: int
    unsure: int


def unknown_merchants(conn: sqlite3.Connection) -> list[dict[str, object]]:
    """Counted spending without a category, one entry per merchant, biggest money first."""
    return _describe(
        conn.execute(
            "SELECT merchant_key, counterparty, location, kind, amount_minor FROM transactions "
            "WHERE category IS NULL AND merchant_key IS NOT NULL "
            "AND status IN ('settled', 'pending')"
        ).fetchall()
    )


def suggest_categories(
    conn: sqlite3.Connection, model: ChatModel, config: CategoryConfig, limit: int | None = None
) -> SuggestResult:
    choices = [c for c in config.categories.values() if c.kind.value in SPEND_KINDS]
    names = tuple(c.name for c in choices)
    merchants = unknown_merchants(conn)[:limit]
    if not merchants or not names:
        return SuggestResult(0, 0, 0)
    fallback = "Other" if "Other" in names else names[-1]
    system = prompt("categorize.md").format(
        categories="\n".join(f"- {c.name} — {c.kind.value} — {c.description}" for c in choices),
        fallback=fallback,
        examples=_owner_examples(conn, names),
    )
    schema = _answer_schema(names)
    asked = {str(m["merchant"]) for m in merchants}
    suggestions = []
    for start in range(0, len(merchants), BATCH):
        batch = merchants[start : start + BATCH]
        answer = model.chat(system, json.dumps(batch, ensure_ascii=False), schema, think="medium")
        suggestions += [
            Suggestion(item.merchant, item.category, item.confidence)
            for item in answer.items  # type: ignore[attr-defined]
            if item.merchant in asked  # the model may invent or rewrite a name
        ]
    with conn:
        save_suggestions(conn, suggestions, model.model, now_local_iso())
    confident = sum(1 for s in suggestions if s.confidence >= CONFIDENT and s.category != fallback)
    return SuggestResult(len(merchants), confident, len(suggestions) - confident)


def _owner_examples(conn: sqlite3.Connection, names: tuple[str, ...]) -> str:
    """How the owner sorted the most frequent merchants: the model follows their taxonomy
    (a drugstore is beauty, not pharmacy; Vinted is clothes, not a marketplace)."""
    rows = conn.execute(
        "SELECT merchant_key, category, COUNT(*) AS n FROM transactions "
        "WHERE category IS NOT NULL AND merchant_key IS NOT NULL AND kind IN ('card', 'blik') "
        "GROUP BY merchant_key, category ORDER BY n DESC"
    ).fetchall()
    seen: dict[str, str] = {}
    for row in rows:
        if row["category"] in names and row["merchant_key"] not in seen:
            seen[row["merchant_key"]] = row["category"]
    picked = list(seen.items())[:EXAMPLES]
    return "\n".join(f"- {merchant} -> {category}" for merchant, category in picked) or "(none yet)"


def _describe(rows: list[sqlite3.Row]) -> list[dict[str, object]]:
    grouped: dict[str, list[sqlite3.Row]] = defaultdict(list)
    for row in rows:
        grouped[row["merchant_key"]].append(row)
    ordered = sorted(grouped.items(), key=lambda kv: sum(r["amount_minor"] for r in kv[1]))
    return [
        {
            "merchant": key,
            "as_printed": sorted({r["counterparty"] for r in items if r["counterparty"]})[:3],
            "cities": sorted({r["location"] for r in items if r["location"]})[:2],
            "operation": [
                k for k, _ in collections.Counter(r["kind"] for r in items).most_common()
            ],
            "payments": len(items),
            "typical_amount_zl": round(
                statistics.median(-r["amount_minor"] for r in items) / 100, 2
            ),
        }
        for key, items in ordered
    ]


def _answer_schema(names: tuple[str, ...]) -> type[BaseModel]:
    item = create_model(
        "MerchantCategory",
        merchant=(str, ...),
        category=(Literal[names], ...),  # type: ignore[valid-type]
        confidence=(float, Field(ge=0, le=1)),
    )
    return create_model("MerchantCategories", items=(list[item], ...))  # type: ignore[valid-type]
