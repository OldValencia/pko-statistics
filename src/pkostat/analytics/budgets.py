"""The month against the owner's plan: category limits and the saving goal."""

from datetime import date

from pkostat.analytics.model_plan import BudgetLine, GoalStatus
from pkostat.analytics.months import MonthTotals
from pkostat.analytics.patterns import days_in
from pkostat.categorize.config import CategoryConfig
from pkostat.domain import Budget

NEAR_LIMIT = 0.85


def budget_lines(
    now: MonthTotals, budget: Budget, complete: bool, data_until: date, config: CategoryConfig
) -> list[BudgetLine]:
    lines = []
    total_days, elapsed = days_in(now.month), max(1, data_until.day)
    for name, limit in budget.limits.items():
        category = config.categories.get(name)
        if category is None:
            continue  # a limit on a category removed since
        spent = max(0, now.by_category.get(name, 0))
        forecast = None
        if not complete:
            # Rent-like categories are paid once: their spending so far is the month's spending.
            once = category.month_shift_from_day is not None
            forecast = spent if once else round(spent / elapsed * total_days)
        expected = forecast if forecast is not None else spent
        if spent > limit:
            status = "over"
        elif expected > limit or spent >= NEAR_LIMIT * limit:
            status = "near"
        else:
            status = "ok"
        lines.append(
            BudgetLine(
                category=name,
                label=category.display,
                kind=category.kind.value,
                limit=limit,
                spent=spent,
                forecast=forecast,
                status=status,
            )
        )
    return sorted(lines, key=lambda line: (-line.spent / line.limit, line.label))


def goal_status(
    now: MonthTotals,
    budget: Budget,
    complete: bool,
    history: list[MonthTotals],
    data_until: date,
) -> GoalStatus | None:
    if budget.goal is None:
        return None
    if complete:
        return GoalStatus(
            target=budget.goal, complete=True, net=now.net, met=now.net >= budget.goal
        )
    # Salary usually lands at the month's end: plan with the usual income until it arrives.
    usual = round(sum(m.income for m in history) / len(history)) if history else 0
    expected_income = max(now.income, usual)
    left = expected_income - budget.goal - now.spend + now.transfers
    days_left = max(1, days_in(now.month) - data_until.day)
    return GoalStatus(
        target=budget.goal,
        complete=False,
        net=now.net,
        met=None,
        expected_income=expected_income,
        left_to_spend=left,
        per_day=round(left / days_left),
        days_left=days_left,
    )
