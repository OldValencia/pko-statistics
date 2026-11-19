"""Placing transactions into report months and summing each month."""

from collections import Counter
from dataclasses import dataclass, field
from datetime import date

from pkostat.categorize.config import CategoryConfig, CategoryKind
from pkostat.domain import Kind, Transaction

UNCATEGORISED = "Uncategorised"
UNCATEGORISED_KIND = "uncategorised"
SPEND_KINDS = frozenset({"essential", "discretionary", "impulse", "other", UNCATEGORISED_KIND})
# Leaks and wins are about avoidable spending; a health bill is not a screw-up.
AVOIDABLE_KINDS = frozenset({"discretionary", "impulse"})


@dataclass(frozen=True, slots=True)
class Entry:
    """A counted transaction placed in the month it belongs to."""

    tx: Transaction
    month: str
    category: str
    kind: str
    shifted: bool


@dataclass(slots=True)
class MerchantTotal:
    category: str
    total: int = 0
    count: int = 0


@dataclass(slots=True)
class MonthTotals:
    month: str
    income: int = 0
    spend: int = 0  # positive: money spent minus refunds
    transfers: int = 0  # signed sum of transfer-kind operations (people, cash)
    to_people: int = 0  # positive: money sent to people
    by_kind: Counter[str] = field(default_factory=Counter)
    by_category: Counter[str] = field(default_factory=Counter)
    payments: Counter[str] = field(default_factory=Counter)
    merchants: dict[str, MerchantTotal] = field(default_factory=dict)
    entries: list[Entry] = field(default_factory=list)

    @property
    def net(self) -> int:
        return self.income - self.spend + self.transfers

    @property
    def savings_rate(self) -> float | None:
        return self.net / self.income if self.income > 0 else None


def place(transactions: list[Transaction], config: CategoryConfig) -> list[Entry]:
    entries = []
    for tx in transactions:
        if not tx.counted:
            continue
        category = tx.category or UNCATEGORISED
        known = config.categories.get(category)
        kind = known.kind.value if known else UNCATEGORISED_KIND
        shift_day = known.month_shift_from_day if known else None
        day = date.fromisoformat(tx.occurred_on)
        shifted = shift_day is not None and day.day >= shift_day
        month = next_month(tx.occurred_on[:7]) if shifted else tx.occurred_on[:7]
        entries.append(Entry(tx, month, category, kind, shifted))
    return entries


def month_totals(entries: list[Entry]) -> dict[str, MonthTotals]:
    months: dict[str, MonthTotals] = {}
    for entry in entries:
        totals = months.setdefault(entry.month, MonthTotals(entry.month))
        totals.entries.append(entry)
        amount = entry.tx.amount_minor
        if entry.kind == CategoryKind.INCOME:
            totals.income += amount
        elif entry.kind == CategoryKind.TRANSFER:
            totals.transfers += amount
            if entry.tx.kind == Kind.TRANSFER_OUT:
                totals.to_people -= amount
        else:
            _add_spending(totals, entry)
    return dict(sorted(months.items()))


def _add_spending(totals: MonthTotals, entry: Entry) -> None:
    amount = entry.tx.amount_minor
    totals.spend -= amount
    totals.by_kind[entry.kind] -= amount
    totals.by_category[entry.category] -= amount
    if amount < 0:
        totals.payments[entry.category] += 1
        key = entry.tx.merchant_key or entry.tx.counterparty or "?"
        merchant = totals.merchants.setdefault(key, MerchantTotal(entry.category))
        merchant.total -= amount
        merchant.count += 1


def next_month(month: str) -> str:
    year, number = int(month[:4]), int(month[5:7])
    return f"{year + number // 12}-{number % 12 + 1:02d}"


def previous_month(month: str) -> str:
    year, number = int(month[:4]), int(month[5:7])
    return f"{year - 1}-12" if number == 1 else f"{year}-{number - 1:02d}"
