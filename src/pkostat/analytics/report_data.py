"""Assembling everything the report page shows, for every month at once (the page switches months
without asking the server, and the published HTML has no server at all)."""

from datetime import date, datetime

from pkostat.analytics import budgets, findings, overview, patterns
from pkostat.analytics.model import (
    CategoryInfo,
    MonthNotes,
    MonthReport,
    MonthSummary,
    ReportData,
    TopMerchant,
    TransactionRow,
)
from pkostat.analytics.months import (
    UNCATEGORISED,
    Entry,
    MonthTotals,
    month_totals,
    place,
    previous_month,
)
from pkostat.analytics.story import month_story
from pkostat.categorize.config import CategoryConfig
from pkostat.domain import Budget, Status, Transaction

TOP_MERCHANTS = 10


def build_report_data(
    user: str,
    transactions: list[Transaction],
    config: CategoryConfig,
    today: date,
    start_month: str | None = None,
    budget: Budget | None = None,
) -> ReportData:
    entries = place(transactions, config)
    placed_by_id = {id(e.tx): e for e in entries}
    totals = month_totals(entries)
    months = [m for m in totals if start_month is None or m >= start_month]
    data_until = max((date.fromisoformat(t.occurred_on) for t in transactions), default=today)
    current_month = today.strftime("%Y-%m")
    complete = [m for m in months if m < current_month]
    series = {m: _summary(totals[m], m in complete) for m in months}
    plan = budget or Budget()
    reports = {m: _month_report(m, totals, series, plan, data_until, config) for m in months}
    return ReportData(
        user=user,
        generated_at=datetime.now().isoformat(timespec="minutes"),
        data_until=data_until.isoformat(),
        months=months,
        series=list(series.values()),
        reports=reports,
        categories=[
            CategoryInfo(name=c.name, label=c.display, kind=c.kind.value)
            for c in config.categories.values()
        ],
        recurring=patterns.recurring(entries, data_until, config),
        ytd=overview.year_to_date(complete, totals, config),
        what_if=overview.what_if(complete, totals, config),
        transactions=[_row(t, placed_by_id) for t in transactions],
        unmatched_holds=sum(1 for t in transactions if t.status == Status.UNMATCHED),
    )


def _summary(t: MonthTotals, complete: bool) -> MonthSummary:
    return MonthSummary(
        month=t.month,
        complete=complete,
        income=t.income,
        spend=t.spend,
        transfers=t.transfers,
        to_people=t.to_people,
        net=t.net,
        savings_rate=t.savings_rate,
        by_kind=dict(t.by_kind),
        by_category=dict(t.by_category),
    )


def _month_report(
    month: str,
    totals: dict[str, MonthTotals],
    series: dict[str, MonthSummary],
    plan: Budget,
    data_until: date,
    config: CategoryConfig,
) -> MonthReport:
    now = totals[month]
    # Only months of the report count as "previous" or "usual": a stray booking from before the
    # first statement (96 zł of December) made January's delivery "+2554 %".
    previous = totals.get(previous_month(month)) if previous_month(month) in series else None
    history = [m for m in _history(month, totals) if m.month in series]
    average = findings.baseline(history)
    leaks, wins = findings.leaks_and_wins(now, average, history, config) if history else ([], [])
    complete = series[month].complete
    last_day = patterns.days_in(month) if complete else data_until.day
    rows = findings.category_rows(now, previous, average, config)
    pace = patterns.pace(now, previous, history, last_day, config)
    lines = budgets.budget_lines(now, plan, complete, data_until, config)
    goal = budgets.goal_status(now, plan, complete, history, data_until)
    return MonthReport(
        summary=series[month],
        previous=series.get(previous.month) if previous else None,
        baseline_months=[m.month for m in history],
        categories=rows,
        leaks=leaks,
        wins=wins,
        share=findings.share(now, config),
        pace=pace,
        weekdays=patterns.weekdays([now, *history], data_until),
        top_merchants=_top_merchants(now, config),
        notes=_notes(now),
        budgets=lines,
        goal=goal,
        story=month_story(now, previous, complete, rows, wins, leaks, lines, goal, pace),
    )


def _history(month: str, totals: dict[str, MonthTotals]) -> list[MonthTotals]:
    found, cursor = [], month
    for _ in range(findings.BASELINE_MONTHS):
        cursor = previous_month(cursor)
        if cursor in totals:
            found.append(totals[cursor])
    return found


def _top_merchants(now: MonthTotals, config: CategoryConfig) -> list[TopMerchant]:
    ranked = sorted(now.merchants.items(), key=lambda item: -item[1].total)[:TOP_MERCHANTS]
    out = []
    for name, m in ranked:
        category = config.categories.get(m.category)
        out.append(
            TopMerchant(
                merchant=name,
                category=m.category,
                label=category.display if category else "Без категории",
                kind=category.kind.value if category else "uncategorised",
                total=m.total,
                count=m.count,
            )
        )
    return out


def _notes(now: MonthTotals) -> MonthNotes:
    uncategorised = [e for e in now.entries if e.category == UNCATEGORISED]
    return MonthNotes(
        pending=sum(1 for e in now.entries if e.tx.status == Status.PENDING),
        uncategorised=len(uncategorised),
        uncategorised_total=-sum(e.tx.amount_minor for e in uncategorised),
        shifted_dates=sorted({e.tx.occurred_on for e in now.entries if e.shifted}),
    )


def _row(t: Transaction, placed_by_id: dict[int, Entry]) -> TransactionRow:
    placed = placed_by_id.get(id(t))
    return TransactionRow(
        id=f"{t.source.value[0]}{t.source_id}",
        date=t.occurred_on,
        month=placed.month if placed else t.occurred_on[:7],
        merchant=t.merchant_key or t.counterparty or "",
        raw=t.counterparty or "",
        title=t.title or "",
        category=t.category,
        type=t.kind.value,
        status=t.status.value,
        source=t.source.value,
        amount=t.amount_minor,
    )
