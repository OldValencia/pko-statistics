"""Parsing one statement row into transaction data.

Columns 7+ are 'Key: value' details, e.g. 'Tytuł: …', 'Nazwa odbiorcy: …',
'Lokalizacja: Adres: WOLT Miasto: WARSAW Kraj: POLSKA', 'Data wykonania operacji: 2026-11-10'.
"""

import re
from collections.abc import Sequence
from dataclasses import dataclass

from pkostat.domain import Kind
from pkostat.errors import PkoStatError
from pkostat.ingest.notifications.fields import squash_spaces
from pkostat.ingest.statement.reader import is_pending
from pkostat.money import parse_amount

_LOCATION = re.compile(
    r"^(?:Adres:\s*(?P<address>.*?))?\s*(?:Miasto:\s*(?P<city>.*?))?\s*(?:Kraj:\s*(?P<country>.*?))?$"
)
_EXECUTED = re.compile(r"^(?P<day>\d{4}-\d{2}-\d{2})(?:\s+(?P<time>\d{2}:\d{2}))?")


@dataclass(frozen=True, slots=True)
class StatementEntry:
    occurred_on: str
    occurred_at: str | None
    amount_minor: int
    currency: str
    kind: Kind
    counterparty: str | None
    location: str | None
    title: str | None
    operation: str  # 'Typ transakcji' as exported
    pending: bool  # a hold ('Blokada'), not booked yet


def parse_row(fields: Sequence[str]) -> StatementEntry:
    operation = fields[2].strip()
    amount_minor = parse_amount(fields[3])
    details = parse_details(fields[6:])
    occurred_on, occurred_at = _when(fields, details)
    address, city = _location(details.get("Lokalizacja", ""))
    payee = details.get("Nazwa odbiorcy") or details.get("Nazwa nadawcy")
    title = details.get("Tytuł")
    pending = is_pending(fields)
    return StatementEntry(
        occurred_on=occurred_on,
        occurred_at=occurred_at,
        amount_minor=amount_minor,
        currency=fields[4].strip(),
        kind=_hold_kind(details) if pending else classify(operation, amount_minor),
        counterparty=squash_spaces(address or payee or "") or None,
        location=city,
        title=squash_spaces(title) if title else None,
        operation=operation,
        pending=pending,
    )


def _hold_kind(details: dict[str, str]) -> Kind:
    # 'Blokada' names no operation type; a place or a card number means a card payment.
    if "Lokalizacja" in details or "Numer karty" in details:
        return Kind.CARD
    return Kind.OTHER


def parse_details(fields: Sequence[str]) -> dict[str, str]:
    details: dict[str, str] = {}
    for field in fields:
        key, separator, value = field.strip().lstrip("'").partition(": ")
        if separator and key:
            details[key.strip()] = value.strip()
    return details


def classify(operation: str, amount_minor: int) -> Kind:
    """Kind from 'Typ transakcji'. Direction comes from the sign: PKO labels outgoing phone
    transfers 'Przelew na telefon przychodz.' too."""
    name = operation.lower()
    if "zwrot" in name:
        return Kind.REFUND
    # Stems: Polish inflects them ('w bankomacie', 'we wpłatomacie').
    if "bankoma" in name or "wpłatoma" in name or "atm" in name:
        return Kind.ATM
    if "kartą" in name:
        return Kind.CARD
    if "kod mobilny" in name or "blik" in name:
        return Kind.BLIK
    if "przelew" in name:
        return Kind.TRANSFER_IN if amount_minor > 0 else Kind.TRANSFER_OUT
    return Kind.OTHER


def _when(fields: Sequence[str], details: dict[str, str]) -> tuple[str, str | None]:
    # 'Data wykonania operacji' is the day the card was used; 'Data operacji' the booking day.
    executed = _EXECUTED.match(details.get("Data wykonania operacji", ""))
    if executed is not None:
        day, time = executed["day"], executed["time"]
        return day, f"{day}T{time}:00" if time else None
    for value in (fields[0].strip(), fields[1].strip()):
        if value:
            return value, None
    raise PkoStatError("Row has no date.")


def _location(value: str) -> tuple[str | None, str | None]:
    match = _LOCATION.match(value.strip())
    if match is None:
        return None, None
    address = squash_spaces(match["address"] or "") or None
    city = squash_spaces(match["city"] or "") or None
    return address, city
