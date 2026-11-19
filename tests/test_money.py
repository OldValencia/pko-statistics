import pytest

from pkostat.errors import PkoStatError
from pkostat.money import format_amount, parse_amount


@pytest.mark.parametrize(
    ("text", "minor"),
    [
        ("59,98", 5998),
        ("1943,75", 194375),
        ("1 943,75", 194375),
        ("1\u00a0943,75", 194375),
        ("12 345 678,90", 1234567890),
        ("-1,00", -100),
        ("+50,00", 5000),
        ("- 3,00", -300),
        ("-108.68", -10868),
        ("0,01", 1),
        (" 6,49 ", 649),
    ],
)
def test_parse_amount(text: str, minor: int) -> None:
    assert parse_amount(text) == minor


@pytest.mark.parametrize("text", ["", "abc", "12", "1,5", "1,234", "1 94,00", "--1,00", "1,00 PLN"])
def test_parse_amount_rejects(text: str) -> None:
    with pytest.raises(PkoStatError):
        parse_amount(text)


@pytest.mark.parametrize(
    ("minor", "text"),
    [(194375, "1 943,75"), (-100, "-1,00"), (5, "0,05"), (123456789, "1 234 567,89")],
)
def test_format_amount(minor: int, text: str) -> None:
    assert format_amount(minor) == text
