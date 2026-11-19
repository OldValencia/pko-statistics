"""'Payment card authorization': a card hold, not the final charge.

Payment card authorization
Amount: 59,98 PLN.
Place: Apteka Pod Lipami, Gdansk.
Date: 2026-11-16 16:42:31.
Card no. *1234 to account no. 22..2222.
"""

import re

from pkostat.domain import Kind
from pkostat.errors import PkoStatError
from pkostat.ingest.notifications.fields import parse_fields, squash_spaces, without_final_period
from pkostat.ingest.notifications.model import ParsedNotification
from pkostat.money import parse_amount

_KEYS = ("Amount", "Place", "Date")
_AMOUNT = re.compile(r"^(?P<amount>.+?)\s+(?P<currency>[A-Z]{3})$")
_DATE = re.compile(r"^(?P<day>\d{4}-\d{2}-\d{2}) (?P<time>\d{2}:\d{2}:\d{2})$")


def parse_card_authorization(lines: list[str], received_at: str) -> ParsedNotification | None:
    fields = parse_fields(lines, _KEYS)
    amount = _AMOUNT.match(without_final_period(fields.get("Amount", "")))
    if amount is None:
        return None
    try:
        amount_minor = parse_amount(amount["amount"])
    except PkoStatError:
        return None
    merchant, location = _split_place(without_final_period(fields.get("Place", "")))
    return ParsedNotification(
        occurred_at=_occurred_at(fields.get("Date"), received_at),
        # The push shows the amount unsigned; an authorization always takes money.
        amount_minor=-abs(amount_minor),
        currency=amount["currency"],
        kind=Kind.CARD,
        counterparty=merchant,
        location=location,
        title=None,
    )


def _split_place(place: str) -> tuple[str | None, str | None]:
    """'FOTO PHU, Gdansk' -> ('FOTO PHU', 'Gdansk'); the city is after the last comma."""
    place = squash_spaces(place)
    if not place:
        return None, None
    merchant, separator, city = place.rpartition(", ")
    if not separator:
        return place, None
    return merchant, city or None


def _occurred_at(date: str | None, received_at: str) -> str:
    match = _DATE.match(without_final_period(date)) if date else None
    if match is None:
        return received_at
    return f"{match['day']}T{match['time']}"
