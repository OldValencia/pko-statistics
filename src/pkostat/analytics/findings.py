"""Comparisons of one month against the previous one and the 3-month baseline."""

from pkostat.analytics.model import CategoryRow, Finding, MerchantLine, ShareSlice
from pkostat.analytics.months import AVOIDABLE_KINDS, SPEND_KINDS, MonthTotals
from pkostat.categorize.config import CategoryConfig

BASELINE_MONTHS = 3
MIN_CHANGE = 10_000  # 100 zł: smaller moves are noise
MIN_RELATIVE = 0.15
ONE_OFF_SHARE = 0.6  # a single purchase this big a share of the baseline is not a habit
SHOWN_ROW_MIN = 1_000
FINDINGS_LIMIT = 4
SHARE_SLICES = 5


def baseline(months: list[MonthTotals]) -> dict[str, int]:
    """Average spending per category over the given months."""
    totals: dict[str, int] = {}
    for month in months:
        for category, value in month.by_category.items():
            totals[category] = totals.get(category, 0) + value
    return (
        {category: round(value / len(months)) for category, value in totals.items()}
        if months
        else {}
    )


def top_merchants(month: MonthTotals, category: str, limit: int) -> list[MerchantLine]:
    lines = [
        MerchantLine(merchant=name, total=m.total, count=m.count)
        for name, m in month.merchants.items()
        if m.category == category
    ]
    return sorted(lines, key=lambda line: -line.total)[:limit]


def category_rows(
    now: MonthTotals, previous: MonthTotals | None, average: dict[str, int], config: CategoryConfig
) -> list[CategoryRow]:
    names = set(now.by_category) | set(average) | set(previous.by_category if previous else {})
    rows = []
    for name in names:
        kind = _kind(name, config)
        if kind not in SPEND_KINDS:
            continue
        row = CategoryRow(
            category=name,
            label=_label(name, config),
            kind=kind,
            now=max(0, now.by_category.get(name, 0)),
            previous=max(0, previous.by_category.get(name, 0)) if previous else 0,
            average=max(0, average.get(name, 0)),
            payments=now.payments.get(name, 0),
            top_merchants=top_merchants(now, name, 6),
        )
        if max(row.now, row.previous, row.average) >= SHOWN_ROW_MIN:
            rows.append(row)
    return sorted(rows, key=lambda row: (-row.now, row.label))


def leaks_and_wins(
    now: MonthTotals, average: dict[str, int], history: list[MonthTotals], config: CategoryConfig
) -> tuple[list[Finding], list[Finding]]:
    findings = []
    for name in set(now.by_category) | set(average):
        if _kind(name, config) not in AVOIDABLE_KINDS:
            continue
        current, avg = max(0, now.by_category.get(name, 0)), max(0, average.get(name, 0))
        findings.append(_finding(now, name, current, avg, config))
    leaks = sorted(
        (
            f
            for f in findings
            if f.now - f.average >= MIN_CHANGE and (f.change is None or f.change >= MIN_RELATIVE)
        ),
        key=lambda f: f.average - f.now,
    )[:FINDINGS_LIMIT]
    impulse = [f for f in findings if f.kind == "impulse" and f.now > 0]
    if impulse:
        biggest = max(impulse, key=lambda f: f.now)
        leaks = [f for f in leaks if f.category != biggest.category]
        leaks.insert(0, biggest.model_copy(update={"headline": True}))
        leaks = leaks[:FINDINGS_LIMIT]
    shown = {f.category for f in leaks}
    wins = sorted(
        (
            f
            for f in findings
            if f.average - f.now >= MIN_CHANGE
            and f.change is not None
            and f.change <= -MIN_RELATIVE
            and f.category not in shown
            and not _one_off(history, f.category)
        ),
        key=lambda f: f.now - f.average,
    )[:FINDINGS_LIMIT]
    return leaks, wins


def share(now: MonthTotals, config: CategoryConfig) -> list[ShareSlice]:
    spent = sorted(
        ((name, value) for name, value in now.by_category.items() if value > 0),
        key=lambda item: -item[1],
    )
    slices = [
        ShareSlice(label=_label(name, config), category=name, total=value)
        for name, value in spent[:SHARE_SLICES]
    ]
    rest = spent[SHARE_SLICES:]
    if rest:
        slices.append(
            ShareSlice(
                label=f"Остальное ({len(rest)})", category=None, total=sum(v for _, v in rest)
            )
        )
    return slices


def _finding(
    now: MonthTotals, name: str, current: int, avg: int, config: CategoryConfig
) -> Finding:
    return Finding(
        category=name,
        label=_label(name, config),
        kind=_kind(name, config),
        now=current,
        average=avg,
        change=(current - avg) / avg if avg > 0 else None,
        payments=now.payments.get(name, 0),
        headline=False,
        top_merchants=top_merchants(now, name, 2),
    )


def _one_off(history: list[MonthTotals], category: str) -> bool:
    amounts = [
        -entry.tx.amount_minor
        for month in history
        for entry in month.entries
        if entry.category == category and entry.tx.amount_minor < 0
    ]
    total = sum(amounts)
    return total > 0 and max(amounts) > ONE_OFF_SHARE * total


def _kind(name: str, config: CategoryConfig) -> str:
    category = config.categories.get(name)
    return category.kind.value if category else "uncategorised"


def _label(name: str, config: CategoryConfig) -> str:
    category = config.categories.get(name)
    return category.display if category else "Без категории"
