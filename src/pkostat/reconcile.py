"""Matching provisional records (pushes, statement holds) against more authoritative ones.

A push or a 'Blokada' row is an early sign of an operation that a statement books days later.
Matched provisional records become 'superseded' and drop out of statistics, so nothing is counted
twice. Which record one is paired with does not change any total, only whether it is paired.

Two passes: exact (same amount) for everything first, then "similar" for what is left, so an
exact pair is never stolen by a near one.
"""

from collections.abc import Callable
from dataclasses import replace
from datetime import date, timedelta

from pkostat.domain import Kind, Status, Transaction

# Pushes can arrive a day or two late and card bookings lag the purchase.
MATCH_WINDOW_DAYS = 3
# A record this much older than the statement's end, still unmatched, is not just "not booked yet".
UNMATCHED_AFTER_DAYS = 5
# Card holds get adjusted before booking (Wolt: 273,15 authorised, 268,33 held for one order).
SIMILAR_WINDOW_DAYS = 1
SIMILAR_MAX_DIFFERENCE = 0.10

# A candidate's rank (lower is better) or None when it cannot be the same operation.
Ranker = Callable[[Transaction, Transaction, int], tuple[int, ...] | None]


def reconcile(
    pushes: list[Transaction], statement: list[Transaction], covered_until: str | None
) -> list[Transaction]:
    """Return the provisional records ('pushes') with status superseded, unmatched or pending,
    matched against 'statement', the records that outrank them."""
    if covered_until is None:
        return [replace(push, status=Status.PENDING) for push in pushes]
    last_day = date.fromisoformat(covered_until)
    ordered = sorted(pushes, key=lambda tx: (tx.occurred_at or tx.occurred_on, tx.source_id))
    # Records after the statement's end cannot be in it.
    eligible = [
        i for i, push in enumerate(ordered) if date.fromisoformat(push.occurred_on) <= last_day
    ]
    matches: dict[int, Transaction] = {}
    used: set[int] = set()
    for ranker in (_exact_rank, _similar_rank):
        for index in eligible:
            if index in matches:
                continue
            match = _best(ordered[index], statement, used, ranker)
            if match is not None:
                matches[index] = match
                used.add(match.source_id)
    unmatched_before = last_day - timedelta(days=UNMATCHED_AFTER_DAYS)
    return [
        _with_status(push, matches.get(index), unmatched_before)
        for index, push in enumerate(ordered)
    ]


def _with_status(
    push: Transaction, match: Transaction | None, unmatched_before: date
) -> Transaction:
    if match is not None:
        return replace(push, status=Status.SUPERSEDED, matched_csv_row_id=match.source_id)
    if date.fromisoformat(push.occurred_on) < unmatched_before:
        return replace(push, status=Status.UNMATCHED)
    return replace(push, status=Status.PENDING)


def _best(
    push: Transaction, statement: list[Transaction], used: set[int], ranker: Ranker
) -> Transaction | None:
    best: tuple[tuple[int, ...], Transaction] | None = None
    for tx in statement:
        if tx.source_id in used or tx.currency != push.currency:
            continue
        days = abs((date.fromisoformat(tx.occurred_on) - date.fromisoformat(push.occurred_on)).days)
        rank = ranker(push, tx, days)
        if rank is not None and (
            best is None or (*rank, tx.source_id) < (*best[0], best[1].source_id)
        ):
            best = (rank, tx)
    return None if best is None else best[1]


def _exact_rank(push: Transaction, tx: Transaction, days: int) -> tuple[int, ...] | None:
    if tx.amount_minor != push.amount_minor or days > MATCH_WINDOW_DAYS:
        return None
    return (tx.kind != push.kind, days)


def _similar_rank(push: Transaction, tx: Transaction, days: int) -> tuple[int, ...] | None:
    if push.kind != Kind.CARD or tx.kind != Kind.CARD or days > SIMILAR_WINDOW_DAYS:
        return None
    if (push.amount_minor < 0) != (tx.amount_minor < 0):
        return None
    largest = max(abs(push.amount_minor), abs(tx.amount_minor))
    difference = abs(push.amount_minor - tx.amount_minor)
    if difference > largest * SIMILAR_MAX_DIFFERENCE:
        return None
    if push.merchant_key is None or push.merchant_key != tx.merchant_key:
        return None
    return (days, difference)
