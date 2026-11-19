import json
import re
from datetime import date

from pkostat.analytics.report_data import build_report_data
from pkostat.categorize.config import load_category_config
from pkostat.domain import Kind, Source, Status, Transaction
from pkostat.report.render import render_report

EVIL = "</script><script>alert(1)</script><!--"


def _data():
    salary = Transaction(
        1, Source.CSV, 1, "2026-10-10", None, 900_000, "PLN", Kind.TRANSFER_IN, "ACME", None,
        "Wynagrodzenie", Status.SETTLED, merchant_key="ACME", category="Salary",
    )  # fmt: skip
    shop = Transaction(
        1, Source.CSV, 2, "2026-10-11", None, -5_000, "PLN", Kind.CARD, EVIL, None,
        None, Status.SETTLED, merchant_key=EVIL, category=None,
    )  # fmt: skip
    return build_report_data("Jane <b>", [salary, shop], load_category_config(), date(2026, 11, 18))


def _payload(html: str) -> dict:
    found = re.search(r'<script type="application/json" id="data">(.*?)</script>', html, re.S)
    assert found is not None
    return json.loads(found.group(1))


def test_user_mode_is_read_only() -> None:
    html = render_report(_data(), "user")

    assert 'class="user-mode"' in html
    assert 'data-page="admin"' not in html
    assert "Без категории<span" not in html
    assert _payload(html)["mode"] == "user"


def test_admin_mode_has_admin_pages() -> None:
    html = render_report(_data(), "admin")

    assert 'data-admin="categories"' in html and 'data-admin="users"' in html
    assert 'id="page-admin"' in html


def test_untrusted_text_cannot_break_out_of_the_page() -> None:
    html = render_report(_data(), "user")

    # The merchant name round-trips through the JSON but never closes the script element.
    assert html.count("</script>") == 2
    assert "<script>alert(1)" not in html
    assert _payload(html)["report"]["transactions"][1]["merchant"] == EVIL
    assert "Jane &lt;b&gt;" in html


def test_page_is_self_contained() -> None:
    html = render_report(_data(), "user")

    assert not re.search(r'(src|href)="https?://', html)
    assert "function renderReport" in html and "--essential" in html


def test_published_page_carries_no_admin_data_or_code() -> None:
    html = render_report(_data(), "user", admin={"users": [{"name": "x", "token": "SECRET"}]})

    assert "SECRET" not in html
    assert "admin" not in _payload(html)
    assert "/api/" not in html
