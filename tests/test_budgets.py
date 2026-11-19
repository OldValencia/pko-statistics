import sqlite3
from datetime import date

import pytest

from pkostat.analytics.report_data import build_report_data
from pkostat.categorize.config import CategoryConfig, load_category_config
from pkostat.db.budgets import get_budget, save_budget
from pkostat.domain import Budget, Kind, Source, Status, Transaction
from pkostat.report.render import render_report
from pkostat.users import add_user

TODAY = date(2026, 11, 18)
_ids = iter(range(1, 10_000))


@pytest.fixture(scope="module")
def config() -> CategoryConfig:
    return load_category_config()


def tx(day: str, zl: float, category: str, kind: Kind = Kind.CARD) -> Transaction:
    return Transaction(
        user_id=1, source=Source.CSV, source_id=next(_ids), occurred_on=day, occurred_at=None,
        amount_minor=round(zl * 100), currency="PLN", kind=kind, counterparty="M", location=None,
        title=None, status=Status.SETTLED, merchant_key="M", category=category,
    )  # fmt: skip


def rows() -> list[Transaction]:
    out = []
    for month in ("2026-08", "2026-09", "2026-10"):
        out.append(tx(f"{month}-28", 9000, "Salary", Kind.TRANSFER_IN))
    out += [
        tx("2026-10-01", -3000, "Rent & utilities", Kind.TRANSFER_OUT),
        tx("2026-10-05", -900, "Food delivery"),
        tx("2026-10-06", -170, "Taxi & scooters"),
        tx("2026-10-07", -100, "Clothes & shoes"),
        tx("2026-11-01", -3000, "Rent & utilities", Kind.TRANSFER_OUT),
        tx("2026-11-09", -300, "Food delivery"),
    ]
    return out


PLAN = Budget(
    goal=200_000,
    limits={"Food delivery": 80_000, "Taxi & scooters": 20_000, "Clothes & shoes": 50_000,
            "Rent & utilities": 300_000},
)  # fmt: skip


def test_complete_month_against_plan(config: CategoryConfig) -> None:
    report = build_report_data("A", rows(), config, TODAY, budget=PLAN).reports["2026-10"]

    status = {line.category: (line.spent, line.status, line.forecast) for line in report.budgets}
    assert status == {
        "Food delivery": (90_000, "over", None),
        "Taxi & scooters": (17_000, "near", None),  # 85 % of the limit
        "Clothes & shoes": (10_000, "ok", None),
        "Rent & utilities": (300_000, "near", None),
    }
    assert report.budgets[0].category == "Food delivery"  # worst first
    goal = report.goal
    assert (goal.complete, goal.net, goal.met) == (True, 900_000 - 417_000, True)


def test_running_month_forecast_and_allowance(config: CategoryConfig) -> None:
    data = build_report_data("A", rows(), config, TODAY, budget=PLAN)
    november = data.reports["2026-11"]

    lines = {line.category: line for line in november.budgets}
    # Last data on the 9th: 300 zł in 9 days of 30 → 1 000 zł by the month's end.
    assert (lines["Food delivery"].forecast, lines["Food delivery"].status) == (100_000, "near")
    assert lines["Rent & utilities"].forecast == 300_000  # paid once, no extrapolation
    goal = november.goal
    assert goal.met is None and goal.expected_income == 900_000  # usual salary, not yet in
    assert goal.left_to_spend == 900_000 - 200_000 - 330_000
    assert goal.days_left == 21 and goal.per_day == round(370_000 / 21)


def test_no_plan_no_section(config: CategoryConfig) -> None:
    report = build_report_data("A", rows(), config, TODAY).reports["2026-10"]

    assert report.budgets == [] and report.goal is None


def test_limits_on_removed_categories_are_ignored(config: CategoryConfig) -> None:
    plan = Budget(limits={"Gone": 10_000})

    assert (
        build_report_data("A", rows(), config, TODAY, budget=plan).reports["2026-10"].budgets == []
    )


def test_story_mentions_the_plan(config: CategoryConfig) -> None:
    story = build_report_data("A", rows(), config, TODAY, budget=PLAN).reports["2026-10"].story

    assert "Цель отложить 2 000 zł выполнена." in story.summary
    assert "вышли за лимит «Доставка еды»: 900 zł при лимите 800 zł" in story.summary
    assert story.advice[0].action == "«Доставка еды»: уложиться в лимит 800 zł"
    assert story.advice[0].saving == 10_000


def test_budget_round_trip(db: sqlite3.Connection) -> None:
    user = add_user(db, "alice")
    with db:
        save_budget(db, user.id, PLAN)
    assert get_budget(db, user.id) == PLAN
    with db:
        save_budget(db, user.id, Budget())
    assert get_budget(db, user.id).empty


def test_plan_is_in_the_published_page(config: CategoryConfig) -> None:
    html = render_report(build_report_data("A", rows(), config, TODAY, budget=PLAN), "user")

    assert 'id="planCard"' in html and "renderPlan" in html
