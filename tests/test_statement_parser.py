import pytest
from statement_data import (
    ATM,
    BILL,
    CARD,
    CARD_REFUND,
    CASH_DEPOSIT,
    CASH_IN_CODE,
    PENDING,
    PHONE_IN,
    PHONE_OUT,
    SALARY,
    WEB_BLIK,
)

from pkostat.domain import Kind
from pkostat.ingest.statement.parser import parse_details, parse_row


@pytest.mark.parametrize(
    ("row", "occurred_on", "amount", "kind", "counterparty", "location"),
    [
        (PHONE_IN, "2026-11-12", 5000, Kind.TRANSFER_IN, "JANE DOE", None),
        (PHONE_OUT, "2026-11-11", -12000, Kind.TRANSFER_OUT, "JANE DOE", None),
        (WEB_BLIK, "2026-11-11", -1286, Kind.BLIK, "store.steampowered.com", None),
        (CARD, "2026-11-10", -7021, Kind.CARD, "WOLT", "WARSAW"),
        (SALARY, "2026-10-29", 800000, Kind.TRANSFER_IN, "ACME SPÓŁKA Z O.O.", None),
        (BILL, "2026-11-05", -22021, Kind.TRANSFER_OUT, "JOHN LANDLORD", None),
        (CARD_REFUND, "2026-08-31", 4755, Kind.REFUND, "Pyszne.pl", "Wroclaw"),
        (CASH_DEPOSIT, "2026-03-24", 37000, Kind.ATM, None, "GDANSK"),
        (CASH_IN_CODE, "2026-07-28", 12000, Kind.ATM, None, None),
        (ATM, "2026-01-01", -25000, Kind.ATM, "UL. DLUGA 5", "GDANSK"),
    ],
)
def test_parse_row(
    row: list[str],
    occurred_on: str,
    amount: int,
    kind: Kind,
    counterparty: str | None,
    location: str | None,
) -> None:
    entry = parse_row(row)

    assert entry.occurred_on == occurred_on
    assert entry.amount_minor == amount
    assert entry.kind == kind
    assert entry.counterparty == counterparty
    assert entry.location == location
    assert entry.currency == "PLN"
    assert entry.operation == row[2]


def test_card_uses_execution_date_not_booking_date() -> None:
    entry = parse_row(CARD)

    assert (CARD[0], entry.occurred_on) == ("2026-11-12", "2026-11-10")
    assert entry.occurred_at is None


def test_execution_time_kept_when_present() -> None:
    assert parse_row(CASH_DEPOSIT).occurred_at == "2026-03-24T21:32:00"


def test_title_is_squashed() -> None:
    assert parse_row(PHONE_OUT).title == "PEREVOD NA TELEFON OD: 48500000002 DO: 48500000001"
    assert parse_row(BILL).title == "09-10 2026 PRĄD"


def test_parse_details_strips_quote_and_ignores_free_text() -> None:
    details = parse_details(["'Operacja: 123", "T:485 W:S1BK", "Tytuł: X: Y", ""])

    assert details == {"Operacja": "123", "Tytuł": "X: Y"}


def test_hold_row() -> None:
    entry = parse_row(PENDING)

    assert entry.pending
    assert entry.occurred_on == "2026-11-12"  # no 'Data operacji' yet: 'Data waluty'
    assert (entry.amount_minor, entry.kind) == (-300, Kind.CARD)
    assert (entry.counterparty, entry.location) == ("BOLT.EU/O/2611120000", "Warsaw")


def test_settled_row_is_not_pending() -> None:
    assert not parse_row(CARD).pending
