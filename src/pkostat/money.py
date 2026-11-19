"""The only place amounts are parsed. Money is int grosze everywhere else."""

import re
from decimal import Decimal, InvalidOperation

from pkostat.errors import PkoStatError

# Optional sign, digits with optional space/NBSP thousand separators, ',' or '.' and two decimals.
_AMOUNT = re.compile(
    r"^(?P<sign>[+-]?)\s*(?P<units>\d{1,3}(?:[ \u00a0]?\d{3})*|\d+)[.,](?P<cents>\d{2})$"
)


def parse_amount(text: str) -> int:
    """'1 943,75' -> 194375, '-1,00' -> -100, '+50.00' -> 5000."""
    match = _AMOUNT.match(text.strip())
    if match is None:
        raise PkoStatError(f"Not an amount: {text!r}")
    units = match["units"].replace(" ", "").replace("\u00a0", "")
    try:
        value = Decimal(f"{match['sign']}{units}.{match['cents']}")
    except InvalidOperation as exc:
        raise PkoStatError(f"Not an amount: {text!r}") from exc
    return int(value * 100)


def format_amount(minor: int) -> str:
    """194375 -> '1 943,75' (Polish style, no currency)."""
    sign = "-" if minor < 0 else ""
    units, cents = divmod(abs(minor), 100)
    return f"{sign}{units:,}".replace(",", " ") + f",{cents:02d}"
