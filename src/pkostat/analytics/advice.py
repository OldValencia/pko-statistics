"""Recommendations for a month, each with a saving computed from that month's own numbers."""

from pkostat.analytics.model import CategoryRow, Finding
from pkostat.analytics.model_plan import Advice, BudgetLine
from pkostat.analytics.months import AVOIDABLE_KINDS, MonthTotals
from pkostat.analytics.texts import in_month, plural, zl

FREQUENT = 10  # "no more than ten times a month"
MAX_ADVICE = 3
WORTH_IT = 5_000  # advice saving less than 50 zł a month is noise


def month_advice(
    now: MonthTotals, rows: list[CategoryRow], leaks: list[Finding], budgets: list[BudgetLine]
) -> list[Advice]:
    """Three ways to save, biggest first, one per category: back within a limit the owner set,
    back to the usual level of what grew, or fewer of the small frequent purchases."""
    when = in_month(now.month).capitalize()
    found: list[Advice] = []
    for b in budgets:
        if b.spent > b.limit:
            found.append(
                Advice(
                    category=b.category,
                    label=b.label,
                    saving=b.spent - b.limit,
                    action=f"«{b.label}»: уложиться в лимит {zl(b.limit)}",
                    reason=f"{when} {zl(b.spent)} при лимите {zl(b.limit)}.",
                )
            )
    for f in leaks:
        if not f.headline and f.now > f.average > 0:
            growth = round((f.change or 0) * 100)
            top = f", в основном {f.top_merchants[0].merchant}" if f.top_merchants else ""
            found.append(
                Advice(
                    category=f.category,
                    label=f.label,
                    saving=f.now - f.average,
                    action=f"«{f.label}»: вернуться к обычным {zl(f.average)} в месяц",
                    reason=f"{when} {zl(f.now)}, на {growth}% больше среднего за 3 месяца{top}.",
                )
            )
    for r in rows:
        if r.kind in AVOIDABLE_KINDS and r.payments > FREQUENT:
            ticket = r.now / r.payments
            payments = plural(r.payments, "платёж", "платежа", "платежей")
            found.append(
                Advice(
                    category=r.category,
                    label=r.label,
                    saving=round((r.payments - FREQUENT) * ticket),
                    action=f"«{r.label}»: не чаще {FREQUENT} раз в месяц",
                    reason=f"{when} {payments}, в среднем по {zl(ticket)}.",
                )
            )
    best: dict[str, Advice] = {}
    for advice in found:
        kept = best.get(advice.category)
        if (advice.saving or 0) >= WORTH_IT and (advice.saving or 0) > (
            kept.saving or 0 if kept else 0
        ):
            best[advice.category] = advice
    return sorted(best.values(), key=lambda a: -(a.saving or 0))[:MAX_ADVICE]


def budget_watch(budgets: list[BudgetLine]) -> list[Advice]:
    """While the month runs: the limits it is heading past, while there is time to brake."""
    watch = sorted(
        (b for b in budgets if b.status in ("near", "over")),
        key=lambda b: -((b.forecast or b.spent) - b.limit),
    )
    return [
        Advice(
            category=b.category,
            label=b.label,
            saving=None,
            action=f"«{b.label}»: притормозить",
            reason=(
                f"Потрачено {zl(b.spent)} из {zl(b.limit)}; "
                f"при этом темпе к концу месяца выйдет {zl(b.forecast or b.spent)}."
            ),
        )
        for b in watch
    ][:MAX_ADVICE]
