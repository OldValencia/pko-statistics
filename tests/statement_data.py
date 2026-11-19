"""Anonymised iPKO statement rows: one per transaction type seen in a real export."""

import csv
from collections.abc import Sequence
from pathlib import Path

HEADER = [
    "Data operacji",
    "Data waluty",
    "Typ transakcji",
    "Kwota",
    "Waluta",
    "Saldo po transakcji",
    "Opis transakcji",
]

PENDING = ["", "2026-11-12", "Blokada", "-3.00", "PLN", "W rozliczeniu", "Tytuł: P0001  ",
           "Lokalizacja: Adres: BOLT.EU/O/2611120000 Miasto: Warsaw Kraj: POLSKA"]  # fmt: skip
PHONE_IN = ["2026-11-12", "2026-11-12", "Przelew na telefon przychodz. wew.", "+50.00", "PLN",
            "+1500.00", "Rachunek nadawcy: 11 1111", "Nazwa nadawcy: JANE DOE",
            "Tytuł: MOBILE TRANSFER  OD: 48500000001 DO: 48500000002",
            "Referencje własne zleceniodawcy: 1"]  # fmt: skip
# PKO labels outgoing phone transfers "przychodz." too; only the sign tells the direction.
PHONE_OUT = ["2026-11-11", "2026-11-11", "Przelew na telefon przychodz. wew.", "-120.00", "PLN",
             "+1450.00", "Rachunek odbiorcy: 11 1111", "Nazwa odbiorcy: JANE DOE",
             "Tytuł: PEREVOD NA TELEFON  OD: 48500000002 DO: 48500000001"]  # fmt: skip
WEB_BLIK = ["2026-11-11", "2026-11-11", "Płatność web - kod mobilny", "-12.86", "PLN", "+1570.00",
            "Tytuł: 00000012345678901  ", "Numer telefonu: 48500000002",
            "Lokalizacja: Adres: store.steampowered.com", "'Operacja: 00000012345678901",
            "Numer referencyjny: 00000012345678901"]  # fmt: skip
CARD = ["2026-11-12", "2026-11-10", "Płatność kartą", "-70.21", "PLN", "+1582.86",
        "Tytuł: 012345678 12345678901234567890123 ",
        "Lokalizacja: Adres: WOLT Miasto: WARSAW Kraj: POLSKA",
        "Data wykonania operacji: 2026-11-10", "Oryginalna kwota operacji: 70.21",
        "Numer karty: 425125******1234"]  # fmt: skip
SALARY = ["2026-10-29", "2026-10-29", "Przelew na konto", "+8000.00", "PLN", "+8323.89",
          "Rachunek nadawcy: 22 2222", "Nazwa nadawcy: ACME SPÓŁKA Z O.O.",
          "Adres nadawcy: UL. TESTOWA 1", "Tytuł: Wynagrodzenie za miesiąc 10.2026."]  # fmt: skip
BILL = ["2026-11-05", "2026-11-05", "Przelew z rachunku", "-220.21", "PLN", "+3000.00",
        "Rachunek odbiorcy: 33 3333", "Nazwa odbiorcy: JOHN LANDLORD",
        "Tytuł: 09-10 2026 PRĄD  "]  # fmt: skip
CARD_REFUND = ["2026-09-02", "2026-08-31", "Zwrot płatności kartą", "+47.55", "PLN", "+5000.00",
               "Tytuł: 087654321 32109876543210987654321 ",
               "Lokalizacja: Adres: Pyszne.pl Miasto: Wroclaw Kraj: POLSKA",
               "Data wykonania operacji: 2026-08-31"]  # fmt: skip
CASH_DEPOSIT = ["2026-03-24", "2026-03-24", "Wpłata gotówki we wpłatomacie", "+370.00", "PLN",
                "+2000.00", "Tytuł: PKO BP 10200000", "Lokalizacja: Miasto: GDANSK Kraj: POLSKA",
                "Data wykonania operacji: 2026-03-24 21:32"]  # fmt: skip
CASH_IN_CODE = ["2026-07-28", "2026-07-28", "CASH_IN_ATM_TX_CODE", "+120.00", "PLN", "+1800.00",
                "T:48500000002 W:S1XX0002"]  # fmt: skip
ATM = ["2026-01-01", "2025-12-31", "Wypłata w bankomacie - kod mobilny", "-250.00", "PLN",
       "+5500.00", "Tytuł: S1XX0001",
       "Lokalizacja: Adres: UL. DLUGA 5 Miasto: GDANSK Kraj: POLSKA",
       "Bankomat: S1XX0001"]  # fmt: skip

SETTLED = [PHONE_IN, PHONE_OUT, WEB_BLIK, CARD, SALARY, BILL, CARD_REFUND, CASH_DEPOSIT,
           CASH_IN_CODE, ATM]  # fmt: skip


def write_statement(path: Path, rows: Sequence[Sequence[str]], encoding: str = "cp1250") -> Path:
    """Write rows the way iPKO does: 13 quoted columns, cp1250."""
    with path.open("w", encoding=encoding, newline="") as file:
        writer = csv.writer(file, quoting=csv.QUOTE_ALL)
        for row in [HEADER, *rows]:
            writer.writerow([*row, *[""] * (13 - len(row))])
    return path
