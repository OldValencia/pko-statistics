from pathlib import Path

import pytest
from statement_data import CARD, PENDING, PHONE_IN, SETTLED, write_statement

from pkostat.errors import PkoStatError
from pkostat.ingest.statement.reader import read_statement, row_key

NAME = "Zestawienie operacji za 01.01.2026 - 12.11.2026.csv"


def test_reads_cp1250_including_holds(tmp_path: Path) -> None:
    path = write_statement(tmp_path / NAME, [PENDING, *SETTLED])

    statement = read_statement(path)

    assert len(statement.rows) == len(SETTLED) + 1
    assert statement.pending_rows == 1
    assert statement.rows[3][2] == "Płatność web - kod mobilny"
    assert (statement.period_from, statement.period_to) == ("2026-01-01", "2026-11-12")
    assert len(statement.sha256) == 64


def test_utf8_file_is_accepted(tmp_path: Path) -> None:
    path = write_statement(tmp_path / NAME, [CARD], encoding="utf-8")

    assert read_statement(path).rows[0][2] == "Płatność kartą"


def test_period_from_rows_when_name_has_none(tmp_path: Path) -> None:
    path = write_statement(tmp_path / "export.csv", [PHONE_IN, CARD])

    statement = read_statement(path)

    assert (statement.period_from, statement.period_to) == ("2026-11-10", "2026-11-12")


def test_wrong_header_rejected(tmp_path: Path) -> None:
    path = tmp_path / "other.csv"
    path.write_text('"Date","Amount"\n"2026-01-01","1.00"\n', encoding="utf-8")

    with pytest.raises(PkoStatError, match="not an iPKO statement"):
        read_statement(path)


def test_missing_file(tmp_path: Path) -> None:
    with pytest.raises(PkoStatError, match="No such file"):
        read_statement(tmp_path / "nope.csv")


def test_row_key_ignores_padding_and_whitespace() -> None:
    padded = (*CARD, "", "")
    spaced = tuple(f" {field} " for field in CARD)

    assert row_key(CARD) == row_key(padded) == row_key(spaced)
    assert row_key(CARD) != row_key(PHONE_IN)
