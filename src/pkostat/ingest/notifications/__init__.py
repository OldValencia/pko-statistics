"""Parsing IKO push notifications (English app language) into transaction data.

Each notification type has its own module; the header (first non-empty line) picks the parser.
Unknown headers return None and the notification counts as unparsed.
"""

from collections.abc import Callable

from pkostat.ingest.notifications.account import parse_account_operation
from pkostat.ingest.notifications.card import parse_card_authorization
from pkostat.ingest.notifications.model import ParsedNotification

_PARSERS: dict[str, Callable[[list[str], str], ParsedNotification | None]] = {
    "Payment card authorization": parse_card_authorization,
    "Account debit": parse_account_operation,
    "Account credit": parse_account_operation,
}


def notification_header(text: str) -> str:
    return next((line.strip() for line in text.splitlines() if line.strip()), "")


def duplicate_key(text: str) -> str | None:
    """Key under which re-sent copies of one push collide (e.g. the Shortcut fired twice).

    Identical text means the same event only when the text pins it down: card pushes carry the
    timestamp to the second, account pushes the balance after the operation. Without either, two
    identical texts may be two real purchases, so no key is given and both are kept.
    """
    lines = [" ".join(line.split()) for line in text.splitlines()]
    normalized = "\n".join(line for line in lines if line)
    if "\nDate:" in normalized or "\nAvailable balance:" in normalized:
        return normalized
    return None


def parse_notification(text: str, received_at: str) -> ParsedNotification | None:
    """received_at (local ISO) is the fallback when the text carries no date."""
    parser = _PARSERS.get(notification_header(text))
    if parser is None:
        return None
    return parser(text.splitlines(), received_at)


__all__ = ["ParsedNotification", "duplicate_key", "notification_header", "parse_notification"]
