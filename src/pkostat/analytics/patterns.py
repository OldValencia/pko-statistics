"""Patterns across days and months: spending pace, weekdays, recurring payments."""

import calendar
import statistics
from collections import defaultdict
from datetime import date

from pkostat.analytics.model import Pace, Recurring, Weekdays
from pkostat.analytics.months import SPEND_KINDS, Entry, MonthTotals
from pkostat.categorize.config import CategoryConfig
from pkostat.domain import Kind

RECURRING_MIN_MONTHS = 4
RECURRING_MAX_SPREAD = 0.15  # standard deviation relative to the mean price
RECURRING_MAX_PRICE = 20_000
STOPPED_AFTER_DAYS = 45


def days_in(month: str) -> int:
    return calendar.monthrange(int(month[:4]), int(month[5:7]))[1]


def cumulative(month: MonthTotals | None, config: CategoryConfig) -> list[int]:
    """Spending by day of month, accumulated. Month-shifted categories (rent) are left out:
    they land on day 1 or 30 and say nothing about pace."""
    daily = [0] * 31
    for entry in month.entries if month else []:
        category = config.categories.get(entry.category)
        if entry.kind not in SPEND_KINDS or (category and category.month_shift_from_day):
            continue
        day = 1 if entry.shifted else int(entry.tx.occurred_on[8:10])
        daily[day - 1] -= entry.tx.amount_minor
    total, out = 0, []
    for value in daily:
        total += value
        out.append(total)
    return out


def pace(
    now: MonthTotals,
    previous: MonthTotals | None,
    history: list[MonthTotals],
    last_day: int,
    config: CategoryConfig,
) -> Pace:
    curves = [cumulative(month, config) for month in history]
    average = (
        [round(sum(c[i] for c in curves) / len(curves)) for i in range(31)] if curves else [0] * 31
    )
    return Pace(
        current=cumulative(now, config)[:last_day],
        previous=cumulative(previous, config) if previous else [],
        average=average,
        last_day=last_day,
    )


def weekdays(months: list[MonthTotals], data_until: date) -> Weekdays:
    totals, days = [0] * 7, [0] * 7
    for month in months:
        year, number = int(month.month[:4]), int(month.month[5:7])
        last = days_in(month.month)
        if (year, number) == (data_until.year, data_until.month):
            last = data_until.day
        for day in range(1, last + 1):
            days[date(year, number, day).weekday()] += 1
        for entry in month.entries:
            if entry.kind == "impulse" and entry.tx.amount_minor < 0:
                totals[date.fromisoformat(entry.tx.occurred_on).weekday()] -= entry.tx.amount_minor
    return Weekdays(
        months=[month.month for month in months],
        average_per_day=[round(t / d) if d else 0 for t, d in zip(totals, days, strict=True)],
        totals=totals,
    )


def recurring(entries: list[Entry], data_until: date, config: CategoryConfig) -> list[Recurring]:
    """Once a month, every month seen, a stable price: a subscription, not a lunch place."""
    by_merchant: dict[str, list[Entry]] = defaultdict(list)
    for entry in entries:
        if (
            entry.tx.amount_minor < 0
            and entry.tx.kind in (Kind.CARD, Kind.BLIK)
            and entry.tx.merchant_key
        ):
            by_merchant[entry.tx.merchant_key].append(entry)
    found = []
    for merchant, items in by_merchant.items():
        months = {entry.tx.occurred_on[:7] for entry in items}
        prices = [-entry.tx.amount_minor for entry in items]
        mean = statistics.fmean(prices)
        if (
            len(months) < RECURRING_MIN_MONTHS
            or len(items) != len(months)
            or mean > RECURRING_MAX_PRICE
        ):
            continue
        if statistics.pstdev(prices) >= RECURRING_MAX_SPREAD * mean:
            continue
        latest = max(items, key=lambda entry: entry.tx.occurred_on)
        category = config.categories.get(latest.category)
        found.append(
            Recurring(
                merchant=merchant,
                category=latest.category,
                label=category.display if category else "Без категории",
                price=-latest.tx.amount_minor,
                last_charge=latest.tx.occurred_on,
                months=len(months),
                active=(data_until - date.fromisoformat(latest.tx.occurred_on)).days
                <= STOPPED_AFTER_DAYS,
            )
        )
    return sorted(found, key=lambda r: (not r.active, -r.price))
