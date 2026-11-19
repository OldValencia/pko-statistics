from datetime import date

import pytest

from pkostat.analytics.months import month_totals, next_month, place, previous_month
from pkostat.analytics.report_data import build_report_data
from pkostat.categorize.config import CategoryConfig, load_category_config
from pkostat.domain import Kind, Source, Status, Transaction

TODAY = date(2026, 11, 18)
_ids = iter(range(1, 10_000))


@pytest.fixture(scope="module")
def config() -> CategoryConfig:
    return load_category_config()


def tx(
    day: str,
    amount_zl: float,
    category: str | None,
    merchant: str = "SHOP",
    kind: Kind = Kind.CARD,
    status: Status = Status.SETTLED,
) -> Transaction:
    return Transaction(
        user_id=1,
        source=Source.CSV,
        source_id=next(_ids),
        occurred_on=day,
        occurred_at=None,
        amount_minor=round(amount_zl * 100),
        currency="PLN",
        kind=kind,
        counterparty=merchant,
        location=None,
        title=None,
        status=status,
        merchant_key=merchant,
        category=category,
    )


def salary(month: str) -> Transaction:
    return tx(f"{month}-10", 9000, "Salary", "ACME", Kind.TRANSFER_IN)


def test_month_arithmetic() -> None:
    assert next_month("2026-12") == "2027-01"
    assert previous_month("2026-01") == "2025-12"
    assert next_month("2026-09") == "2026-10"


def test_totals_net_and_transfers(config: CategoryConfig) -> None:
    rows = [
        salary("2026-10"),
        tx("2026-10-02", -100, "Food delivery", "WOLT"),
        tx("2026-10-03", 20, "Food delivery", "WOLT", Kind.REFUND),
        tx("2026-10-04", -300, "Transfers to people", "JANE", Kind.TRANSFER_OUT),
        tx("2026-10-05", 50, "Transfers from people", "JANE", Kind.TRANSFER_IN),
        tx("2026-10-06", -999, "Food delivery", "WOLT", status=Status.SUPERSEDED),
        tx("2026-10-07", -40, None, "MYSTERY"),
    ]

    october = month_totals(place(rows, config))["2026-10"]

    assert (october.income, october.spend) == (900_000, 12_000)  # 100 - 20 refund + 40
    assert (october.transfers, october.to_people) == (-25_000, 30_000)
    assert october.net == 900_000 - 12_000 - 25_000
    assert october.by_kind["impulse"] == 8_000
    assert october.by_category["Uncategorised"] == 4_000
    assert october.payments["Food delivery"] == 1  # refunds are not payments


def test_rent_paid_late_counts_in_next_month(config: CategoryConfig) -> None:
    rows = [tx("2026-09-30", -2300, "Rent & utilities", "LANDLORD", Kind.TRANSFER_OUT)]

    data = build_report_data("A", [*rows, salary("2026-10")], config, TODAY)

    assert data.reports["2026-10"].summary.by_category == {"Rent & utilities": 230_000}
    assert data.reports["2026-10"].notes.shifted_dates == ["2026-09-30"]
    assert data.transactions[0].month == "2026-10"


def test_leaks_wins_and_headline(config: CategoryConfig) -> None:
    rows = [salary(m) for m in ("2026-07", "2026-08", "2026-09", "2026-10")]
    for month in ("2026-07", "2026-08", "2026-09"):
        rows += [
            tx(f"{month}-05", -1000, "Food delivery", "WOLT"),
            tx(f"{month}-06", -100, "Clothes & shoes", "ZARA"),
            tx(f"{month}-07", -500, "Online marketplaces", "ALLEGRO"),
            tx(f"{month}-08", -50, "Health & pharmacy", "APTEKA"),
        ]
    rows.append(tx("2026-07-20", -3000, "Electronics", "IDREAM"))  # one-off in the baseline
    rows += [
        tx("2026-10-05", -900, "Food delivery", "WOLT"),
        tx("2026-10-06", -400, "Clothes & shoes", "ZARA"),
        tx("2026-10-07", -100, "Online marketplaces", "ALLEGRO"),
        tx("2026-10-08", -900, "Health & pharmacy", "APTEKA"),
    ]

    report = build_report_data("A", rows, config, TODAY).reports["2026-10"]

    leaks = [(f.category, f.headline) for f in report.leaks]
    assert leaks == [("Food delivery", True), ("Clothes & shoes", False)]
    # Health grew too, but essential spending is not a leak; Electronics was a one-off.
    assert [f.category for f in report.wins] == ["Online marketplaces"]
    assert report.baseline_months == ["2026-09", "2026-08", "2026-07"]


def test_recurring_and_stopped(config: CategoryConfig) -> None:
    rows = []
    for month in ("2026-05", "2026-06", "2026-07", "2026-08", "2026-09", "2026-10", "2026-11"):
        rows.append(tx(f"{month}-02", -29.99, "Subscriptions & software", "YOUTUBE PREMIUM"))
    for month in ("2026-03", "2026-04", "2026-05", "2026-06"):
        rows.append(tx(f"{month}-15", -18.99, "Subscriptions & software", "1PASSWORD"))
    for month in ("2026-08", "2026-09", "2026-10", "2026-11"):
        rows.append(tx(f"{month}-03", -150, "Restaurants & cafes", "SPHINX"))
        rows.append(tx(f"{month}-20", -150, "Restaurants & cafes", "SPHINX"))  # twice a month

    found = build_report_data("A", rows, config, TODAY).recurring

    assert [(r.merchant, r.price, r.active) for r in found] == [
        ("YOUTUBE PREMIUM", 2999, True),
        ("1PASSWORD", 1899, False),
    ]


def test_pace_weekdays_and_completeness(config: CategoryConfig) -> None:
    rows = [
        salary("2026-10"),
        tx("2026-10-01", -2300, "Rent & utilities", "LANDLORD", Kind.TRANSFER_OUT),
        tx("2026-10-06", -100, "Food delivery", "WOLT"),  # a Tuesday
        tx("2026-10-20", -50, "Food delivery", "WOLT"),  # a Tuesday
        tx("2026-11-03", -10, "Food delivery", "WOLT"),
    ]

    data = build_report_data("A", rows, config, TODAY)
    october, november = data.reports["2026-10"], data.reports["2026-11"]

    assert october.pace.current[4] == 0 and october.pace.current[5] == 10_000  # rent left out
    assert len(october.pace.current) == 31
    assert len(november.pace.current) == 3  # month in progress: up to the last day with data
    assert october.weekdays.totals[1] == 15_000
    assert october.weekdays.average_per_day[1] == 15_000 // 4  # four Tuesdays in October 2026
    assert [s.complete for s in data.series] == [True, False]


def test_what_if_and_year_to_date(config: CategoryConfig) -> None:
    rows = []
    for month in ("2026-08", "2026-09", "2026-10"):
        rows.append(salary(month))
        rows += [tx(f"{month}-{d:02d}", -50, "Food delivery", "WOLT") for d in range(1, 11)]
        rows.append(tx(f"{month}-11", -200, "Restaurants & cafes", "CAFE"))
        rows.append(tx(f"{month}-01", -3000, "Rent & utilities", "LANDLORD", Kind.TRANSFER_OUT))

    data = build_report_data("A", rows, config, TODAY)

    levers = [
        (lever.category, lever.monthly, lever.payments, lever.by_count)
        for lever in data.what_if.levers
    ]
    assert levers == [
        ("Food delivery", 50_000, 10, True),
        ("Restaurants & cafes", 20_000, 1, False),
    ]
    assert data.ytd.top_impulse_total == 150_000 and data.ytd.top_impulse_payments == 30
    assert data.ytd.biggest_essential_monthly == 300_000


def test_start_month_hides_stray_older_bookings(config: CategoryConfig) -> None:
    rows = [tx("2025-12-30", -10, "Groceries", "LIDL"), salary("2026-01")]

    data = build_report_data("A", rows, config, TODAY, start_month="2026-01")

    assert data.months == ["2026-01"]
