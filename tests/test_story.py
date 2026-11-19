from datetime import date

import pytest

from pkostat.analytics.report_data import build_report_data
from pkostat.analytics.texts import plural, zl
from pkostat.categorize.config import CategoryConfig, load_category_config
from pkostat.domain import Kind, Source, Status, Transaction

TODAY = date(2026, 11, 18)
NB = " "
_ids = iter(range(1, 100_000))


@pytest.fixture(scope="module")
def config() -> CategoryConfig:
    return load_category_config()


def tx(
    day: str, zl_amount: float, category: str, kind: Kind = Kind.CARD, merchant: str = "M"
) -> Transaction:
    return Transaction(
        user_id=1, source=Source.CSV, source_id=next(_ids), occurred_on=day, occurred_at=None,
        amount_minor=round(zl_amount * 100), currency="PLN", kind=kind, counterparty=merchant,
        location=None, title=None, status=Status.SETTLED, merchant_key=merchant, category=category,
    )  # fmt: skip


def month(m: str, delivery: int, orders: int, clothes: float = 0) -> list[Transaction]:
    rows = [tx(f"{m}-27", 9000, "Salary", Kind.TRANSFER_IN)]
    rows += [
        tx(f"{m}-{d % 28 + 1:02d}", -delivery / orders, "Food delivery", merchant="WOLT")
        for d in range(orders)
    ]
    if clothes:
        rows.append(tx(f"{m}-15", -clothes, "Clothes & shoes", merchant="ZARA"))
    return rows


def test_texts_helpers() -> None:
    assert zl(-123456) == f"1{NB}235{NB}zł"
    assert [plural(n, "платёж", "платежа", "платежей") for n in (1, 3, 5, 11, 21)] == [
        "1 платёж", "3 платежа", "5 платежей", "11 платежей", "21 платёж",
    ]  # fmt: skip


def test_first_month_has_nothing_to_compare(config: CategoryConfig) -> None:
    # A stray booking before the first statement must not become a baseline.
    rows = [tx("2025-12-30", -96, "Food delivery"), *month("2026-01", 2600, 32)]

    report = build_report_data("A", rows, config, TODAY, start_month="2026-01").reports["2026-01"]

    assert "первый месяц данных" in report.story.summary
    assert report.leaks == [] and report.wins == [] and report.previous is None


def test_spending_drop_is_told_as_a_drop(config: CategoryConfig) -> None:
    rows = month("2026-09", 3500, 49, clothes=40) + month("2026-10", 3000, 39, clothes=700)

    story = build_report_data("A", rows, config, TODAY).reports["2026-10"].story

    assert (
        "Расходы выросли на 160 zł; больше всего — «Одежда и обувь»: 700 zł вместо 40 zł."
        in story.summary
    )
    rows = month("2026-09", 3500, 49) + month("2026-10", 3000, 39)
    story = build_report_data("A", rows, config, TODAY).reports["2026-10"].story
    assert (
        f"Расходы снизились на 500{NB}zł; сильнее всего — «Доставка еды»: "
        f"3{NB}000{NB}zł вместо 3{NB}500{NB}zł." in story.summary
    )
    assert "выросли" not in story.summary


def test_advice_uses_the_months_own_numbers(config: CategoryConfig) -> None:
    rows = []
    for m, orders in (("2026-07", 50), ("2026-08", 50), ("2026-09", 50), ("2026-10", 20)):
        rows += month(m, orders * 80, orders, clothes=100)
    rows.append(tx("2026-10-20", -900, "Clothes & shoes", merchant="ZARA"))

    advice = build_report_data("A", rows, config, TODAY).reports["2026-10"].story.advice

    assert [(a.action, a.saving) for a in advice] == [
        (f"«Одежда и обувь»: вернуться к обычным 100{NB}zł в месяц", 90_000),
        ("«Доставка еды»: не чаще 10 раз в месяц", 80_000),  # (20 - 10) * 80 zł of October
    ]


def test_running_month_is_not_judged(config: CategoryConfig) -> None:
    rows = [*month("2026-10", 3000, 30), tx("2026-11-05", -300, "Food delivery", merchant="WOLT")]

    report = build_report_data("A", rows, config, TODAY).reports["2026-11"]

    assert report.story.summary.startswith(f"Ноябрь ещё идёт: по 5-е число потрачено 300{NB}zł.")
    assert "к этому же числу в октябре" in report.story.summary
    assert "превысили" not in report.story.summary and report.story.advice == []
