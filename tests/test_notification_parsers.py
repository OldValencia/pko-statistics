from pathlib import Path

import pytest

from pkostat.domain import Kind
from pkostat.ingest.notifications import ParsedNotification, duplicate_key, parse_notification

FIXTURES = Path(__file__).parent / "fixtures" / "notifications"
RECEIVED_AT = "2026-11-18T15:26:41"


def _parse(name: str) -> ParsedNotification | None:
    return parse_notification((FIXTURES / name).read_text(encoding="utf-8"), RECEIVED_AT)


@pytest.mark.parametrize(
    ("fixture", "occurred_at", "amount", "counterparty", "location"),
    [
        ("card_pharmacy.txt", "2026-11-16T16:42:31", -5998, "Apteka Pod Lipami", "Gdansk"),
        ("card_lidl.txt", "2026-11-16T15:20:19", -649, "LIDL DLUGA", "Gdansk"),
        ("card_uber.txt", "2026-11-16T20:54:15", -1094, "UBR* PENDING.UBER.COM", "Amsterdam"),
        ("card_wolt_country.txt", "2026-11-16T11:26:43", -14165, "Wolt", "Poland"),
        ("card_no_period.txt", "2026-11-18T02:25:10", -27315, "WOLT", "WARSAW"),
        (
            "card_no_date_comma_merchant.txt",
            RECEIVED_AT,
            -120450,
            "SKLEP PHU KOWALSKI, ODDZIAL 2",
            "Gdansk",
        ),
    ],
)
def test_card_authorization(
    fixture: str, occurred_at: str, amount: int, counterparty: str, location: str
) -> None:
    parsed = _parse(fixture)

    assert parsed == ParsedNotification(
        occurred_at=occurred_at,
        amount_minor=amount,
        currency="PLN",
        kind=Kind.CARD,
        counterparty=counterparty,
        location=location,
        title=None,
    )


def test_account_credit_with_wrapped_title() -> None:
    parsed = _parse("credit_phone.txt")

    assert parsed == ParsedNotification(
        occurred_at=RECEIVED_AT,
        amount_minor=5000,
        currency="PLN",
        kind=Kind.TRANSFER_IN,
        counterparty="JANE DOE",
        location=None,
        title="PEREVOD NA TELEFON OD: 48500000001 DO: 48500000002",
    )


def test_account_debit_with_messy_whitespace() -> None:
    parsed = _parse("debit_phone.txt")

    assert parsed is not None
    assert parsed.amount_minor == -12000
    assert parsed.kind == Kind.TRANSFER_OUT
    assert parsed.counterparty == "JANE DOE"
    assert parsed.title == "PEREVOD NA TELEFON OD: 48500000002 DO: 48500000001"
    assert parsed.occurred_on == "2026-11-18"


def test_refund_credit() -> None:
    text = "Account credit\n+25,00 PLN Zwrot płatności kartą\n\nSender: SHOP"

    parsed = parse_notification(text, RECEIVED_AT)

    assert parsed is not None
    assert parsed.kind == Kind.REFUND
    assert parsed.amount_minor == 2500


@pytest.mark.parametrize("fixture", ["debit_wrong_sign.txt", "unknown_type.txt"])
def test_unrecognised_returns_none(fixture: str) -> None:
    assert _parse(fixture) is None


@pytest.mark.parametrize(
    "text",
    [
        "",
        "Payment card authorization\nAmount: lots PLN.",
        "Payment card authorization\nPlace: Somewhere, City.",
        "Account debit",
    ],
)
def test_broken_texts_return_none(text: str) -> None:
    assert parse_notification(text, RECEIVED_AT) is None


def _text(name: str) -> str:
    return (FIXTURES / name).read_text(encoding="utf-8")


def test_duplicate_key_ignores_whitespace_noise() -> None:
    text = _text("debit_phone.txt")
    noisy = "\n\n" + text.replace("\n", "  \n\n").replace("JANE DOE", "JANE  DOE")

    assert duplicate_key(text) is not None
    assert duplicate_key(text) == duplicate_key(noisy)


def test_duplicate_key_differs_for_different_events() -> None:
    assert duplicate_key(_text("card_lidl.txt")) != duplicate_key(_text("card_pharmacy.txt"))
    assert duplicate_key(_text("credit_phone.txt")) is not None


def test_no_duplicate_key_without_timestamp_or_balance() -> None:
    # Two identical undated texts can be two real purchases: never collapse them.
    assert duplicate_key(_text("card_no_date_comma_merchant.txt")) is None
