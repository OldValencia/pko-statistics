"""The month in words, built by code from the computed numbers: always right, always the same.

(The local LLM wrote this before; on real data it called a drop "the reason for growth" and quoted
purchases as savings. Every fact here was already computed, so templates say it better.)
Category names are quoted («…») so sentences need no Russian declension of user-made labels.
"""

from pkostat.analytics.advice import budget_watch, month_advice
from pkostat.analytics.model import CategoryRow, Finding, Pace
from pkostat.analytics.model_plan import BudgetLine, GoalStatus, MonthStory
from pkostat.analytics.months import MonthTotals
from pkostat.analytics.texts import in_month, month_name, zl

NOISE = 10_000  # changes under 100 zł are "about the same"


def month_story(
    now: MonthTotals,
    previous: MonthTotals | None,
    complete: bool,
    rows: list[CategoryRow],
    wins: list[Finding],
    leaks: list[Finding],
    budgets: list[BudgetLine],
    goal: GoalStatus | None,
    pace: Pace,
) -> MonthStory:
    if not complete:
        return MonthStory(
            summary=_running(now, previous, goal, budgets, pace), advice=budget_watch(budgets)
        )
    driver, driver_category = _driver(now, previous, rows)
    sentences = [_verdict(now, previous), driver]
    if goal is not None:
        sentences.append(_goal(goal, budgets))
    news = [f for f in wins if f.category != driver_category]  # do not praise the same thing twice
    if news:
        best = max(news, key=lambda f: f.average - f.now)
        sentences.append(
            f"Хорошая новость: «{best.label}» — {zl(best.now)} против обычных {zl(best.average)}."
        )
    return MonthStory(
        summary=" ".join(s for s in sentences if s), advice=month_advice(now, rows, leaks, budgets)
    )


def _verdict(now: MonthTotals, previous: MonthTotals | None) -> str:
    where = in_month(now.month).capitalize()
    if now.net >= 0:
        rate = f" — {round(now.savings_rate * 100)}% дохода" if now.savings_rate is not None else ""
        text = f"{where} удалось отложить {zl(now.net)}{rate}."
    else:
        text = f"{where} расходы превысили доход на {zl(now.net)}."
    if previous is None:
        return text
    diff = now.net - previous.net
    if abs(diff) < NOISE:
        return f"{text} Примерно как {in_month(previous.month)}."
    better = "лучше" if diff > 0 else "хуже"
    return f"{text} Это на {zl(diff)} {better}, чем {in_month(previous.month)}."


def _driver(
    now: MonthTotals, previous: MonthTotals | None, rows: list[CategoryRow]
) -> tuple[str, str | None]:
    """The sentence about what moved spending most, and that category."""
    if previous is None:
        return "Это первый месяц данных — сравнивать пока не с чем.", None
    change = now.spend - previous.spend
    if abs(change) < NOISE:
        return f"Расходы почти не изменились: {zl(now.spend)}.", None
    grew = change > 0
    movers = [
        r for r in rows if (r.now - r.previous > 0) == grew and abs(r.now - r.previous) >= NOISE
    ]
    head = f"Расходы {'выросли' if grew else 'снизились'} на {zl(change)}"
    if not movers:
        return head + ".", None
    top = max(movers, key=lambda r: abs(r.now - r.previous))
    word = "больше всего" if grew else "сильнее всего"
    return f"{head}; {word} — «{top.label}»: {zl(top.now)} вместо {zl(top.previous)}.", top.category


def _goal(goal: GoalStatus, budgets: list[BudgetLine]) -> str:
    text = f"Цель отложить {zl(goal.target)} {'выполнена' if goal.met else 'не выполнена'}."
    over = [b for b in budgets if b.status == "over"]
    if over:
        worst = max(over, key=lambda b: b.spent - b.limit)
        text += (
            f" Сильнее всего вышли за лимит «{worst.label}»: "
            f"{zl(worst.spent)} при лимите {zl(worst.limit)}."
        )
    return text


def _running(
    now: MonthTotals,
    previous: MonthTotals | None,
    goal: GoalStatus | None,
    budgets: list[BudgetLine],
    pace: Pace,
) -> str:
    day = pace.last_day
    name = month_name(now.month)
    text = f"{name} ещё идёт: по {day}-е число потрачено {zl(now.spend)}."
    if previous is not None and pace.current and len(pace.previous) >= day:
        so_far, before = pace.current[day - 1], pace.previous[day - 1]
        diff = so_far - before
        when = in_month(previous.month)
        if abs(diff) < NOISE:
            compare = f"примерно как к этому же числу {when}"
        else:
            compare = (
                f"на {zl(diff)} {'больше' if diff > 0 else 'меньше'}, чем к этому же числу {when}"
            )
        text += f" Без аренды — {zl(so_far)}, {compare}."
    if goal is not None and goal.left_to_spend is not None:
        if goal.left_to_spend >= 0:
            text += (
                f" Чтобы отложить {zl(goal.target)}, до конца месяца можно потратить ещё "
                f"{zl(goal.left_to_spend)} — около {zl(goal.per_day or 0)} в день."
            )
        else:
            text += f" Цель отложить {zl(goal.target)} в этом месяце уже не выполнить."
    return text
