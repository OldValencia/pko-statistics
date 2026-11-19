"""Reading an iPKO 'Zestawienie operacji' CSV export into raw rows."""

import csv
import hashlib
import io
import re
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

from pkostat.errors import PkoStatError

EXPECTED_HEADER = (
    "Data operacji",
    "Data waluty",
    "Typ transakcji",
    "Kwota",
    "Waluta",
    "Saldo po transakcji",
    "Opis transakcji",
)
_PERIOD_IN_NAME = re.compile(r"(\d{2})\.(\d{2})\.(\d{4})\s*-\s*(\d{2})\.(\d{2})\.(\d{4})")
_ISO_DAY = re.compile(r"^\d{4}-\d{2}-\d{2}$")


@dataclass(frozen=True, slots=True)
class Statement:
    file_name: str
    sha256: str
    period_from: str
    period_to: str
    rows: list[tuple[str, ...]]  # all rows, fields as exported, holds included

    @property
    def pending_rows(self) -> int:
        return sum(1 for fields in self.rows if is_pending(fields))


def read_statement(path: Path) -> Statement:
    if not path.is_file():
        raise PkoStatError(f"No such file: {path}")
    return parse_statement(path.name, path.read_bytes())


def parse_statement(file_name: str, data: bytes) -> Statement:
    """The file's bytes as uploaded or read from disk; the name carries the statement period."""
    records = list(csv.reader(io.StringIO(_decode(data), newline="")))
    if not records or tuple(field.strip() for field in records[0][:7]) != EXPECTED_HEADER:
        raise PkoStatError(f"{file_name} is not an iPKO statement: unexpected header.")
    rows: list[tuple[str, ...]] = []
    for number, fields in enumerate(records[1:], start=2):
        if not any(field.strip() for field in fields):
            continue
        if len(fields) < len(EXPECTED_HEADER):
            raise PkoStatError(f"{file_name}, line {number}: too few columns.")
        rows.append(tuple(fields))
    period_from, period_to = _period(file_name, rows)
    return Statement(file_name, hashlib.sha256(data).hexdigest(), period_from, period_to, rows)


def is_pending(fields: Sequence[str]) -> bool:
    """A hold ('Blokada', balance 'W rozliczeniu'): the money is taken, the booking comes later
    and appears as a settled row in a later statement."""
    return fields[2].strip() == "Blokada" or fields[5].strip() == "W rozliczeniu"


def row_key(fields: Sequence[str]) -> str:
    """Identity of a row across overlapping statements; the balance after it makes it unique."""
    meaningful = [field.strip() for field in fields]
    while meaningful and not meaningful[-1]:
        meaningful.pop()
    return hashlib.sha256("\x1f".join(meaningful).encode("utf-8")).hexdigest()


def _decode(data: bytes) -> str:
    # iPKO exports cp1250; accept UTF-8 too in case the file was re-saved by an editor.
    try:
        return data.decode("utf-8-sig")
    except UnicodeDecodeError:
        return data.decode("cp1250")


def _period(file_name: str, rows: list[tuple[str, ...]]) -> tuple[str, str]:
    match = _PERIOD_IN_NAME.search(file_name)
    if match is not None:
        d1, m1, y1, d2, m2, y2 = match.groups()
        return f"{y1}-{m1}-{d1}", f"{y2}-{m2}-{d2}"
    days = sorted(
        day
        for fields in rows
        for day in (fields[0].strip(), fields[1].strip())
        if _ISO_DAY.match(day)
    )
    if not days:
        raise PkoStatError(
            f"{file_name}: cannot tell the statement period (no dates, no period in name)."
        )
    return days[0], days[-1]
