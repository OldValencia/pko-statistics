"""Summaries over several complete months: the year so far and the "what if" baseline."""

from pkostat.analytics import findings
from pkostat.analytics.model import Lever, WhatIf, Ytd
from pkostat.analytics.months import MonthTotals
from pkostat.categorize.config import CategoryConfig

WHAT_IF_LEVERS = 5


def year_to_date(
    complete: list[str], totals: dict[str, MonthTotals], config: CategoryConfig
) -> Ytd | None:
    if not complete:
        return None
    year = complete[-1][:4]
    months = [totals[m] for m in complete if m.startswith(year)]
    spend_by_category: dict[str, int] = {}
    payments: dict[str, int] = {}
    for t in months:
        for name, value in t.by_category.items():
            spend_by_category[name] = spend_by_category.get(name, 0) + value
            payments[name] = payments.get(name, 0) + t.payments.get(name, 0)
    impulse = _top_of_kind(spend_by_category, "impulse", config)
    essential = _top_of_kind(spend_by_category, "essential", config)
    return Ytd(
        months=[t.month for t in months],
        income=sum(t.income for t in months),
        spend=sum(t.spend for t in months),
        net=sum(t.net for t in months),
        impulse=sum(t.by_kind.get("impulse", 0) for t in months),
        top_impulse_label=config.categories[impulse].display if impulse else None,
        top_impulse_total=spend_by_category.get(impulse, 0) if impulse else 0,
        top_impulse_payments=payments.get(impulse, 0) if impulse else 0,
        biggest_essential_label=config.categories[essential].display if essential else None,
        biggest_essential_monthly=round(spend_by_category[essential] / len(months))
        if essential
        else 0,
    )


def what_if(
    complete: list[str], totals: dict[str, MonthTotals], config: CategoryConfig
) -> WhatIf | None:
    months = [totals[m] for m in complete[-findings.BASELINE_MONTHS :]]
    if not months:
        return None
    average = findings.baseline(months)
    payments = {
        name: round(sum(t.payments.get(name, 0) for t in months) / len(months)) for name in average
    }
    candidates = sorted(
        (
            name
            for name in average
            if _kind_of(name, config) in ("impulse", "discretionary") and average[name] > 0
        ),
        key=lambda name: (_kind_of(name, config) != "impulse", -average[name]),
    )[:WHAT_IF_LEVERS]
    levers = [
        Lever(
            category=name,
            label=config.categories[name].display,
            monthly=average[name],
            payments=payments.get(name, 0),
            by_count=index == 0,
        )
        for index, name in enumerate(candidates)
    ]
    return WhatIf(
        months=[t.month for t in months],
        income=round(sum(t.income for t in months) / len(months)),
        net=round(sum(t.net for t in months) / len(months)),
        levers=levers,
    )


def _top_of_kind(by_category: dict[str, int], kind: str, config: CategoryConfig) -> str | None:
    names = [n for n in by_category if _kind_of(n, config) == kind and by_category[n] > 0]
    return max(names, key=lambda n: by_category[n]) if names else None


def _kind_of(name: str, config: CategoryConfig) -> str:
    category = config.categories.get(name)
    return category.kind.value if category else "uncategorised"
