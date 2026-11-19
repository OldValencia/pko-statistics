"""'Account debit' / 'Account credit': money leaving or entering the account.

    Account debit
    -120,00 PLN Przelew na telefon - wysłany
    Receiver Account: 11..1111
    Receiver: JANE DOE
    Title: PEREVOD NA TELEFON OD: 48500000001 DO: 48500000002
    On account no. 22..2222
    Available balance:+1297,66 PLN

These texts carry no date, so the time the push arrived is used.
"""

import re

from pkostat.domain import Kind
from pkostat.errors import PkoStatError
from pkostat.ingest.notifications.fields import parse_fields, squash_spaces
from pkostat.ingest.notifications.model import ParsedNotification
from pkostat.money import parse_amount

_KEYS = ("Receiver Account", "Receiver", "Sender Account", "Sender", "Title")
_AMOUNT_LINE = re.compile(
    r"^(?P<amount>[+-]\s*[\d \u00a0]+,\d{2})\s*(?P<currency>[A-Z]{3})\s+(?P<operation>.+)$"
)


def parse_account_operation(lines: list[str], received_at: str) -> ParsedNotification | None:
    header, amount_line = _first_two_lines(lines)
    match = _AMOUNT_LINE.match(amount_line)
    if match is None:
        return None
    try:
        amount_minor = parse_amount(match["amount"])
    except PkoStatError:
        return None
    is_debit = header == "Account debit"
    # A debit with a '+' (or a credit with a '-') means the format changed: refuse to guess.
    if (amount_minor < 0) != is_debit:
        return None
    fields = parse_fields(lines, _KEYS)
    counterparty = fields.get("Receiver") if is_debit else fields.get("Sender")
    title = fields.get("Title")
    return ParsedNotification(
        occurred_at=received_at,
        amount_minor=amount_minor,
        currency=match["currency"],
        kind=_kind(squash_spaces(match["operation"]), is_debit),
        counterparty=squash_spaces(counterparty) if counterparty else None,
        location=None,
        title=squash_spaces(title) if title else None,
    )


def _first_two_lines(lines: list[str]) -> tuple[str, str]:
    meaningful = [line.strip() for line in lines if line.strip()]
    meaningful += ["", ""]
    return meaningful[0], meaningful[1]


def _kind(operation: str, is_debit: bool) -> Kind:
    # Only phone transfers ("Przelew na telefon") have been seen so far; "Zwrot" is PKO's word
    # for a refund in statements, assumed to carry over to pushes.
    if "zwrot" in operation.lower():
        return Kind.REFUND
    return Kind.TRANSFER_OUT if is_debit else Kind.TRANSFER_IN
