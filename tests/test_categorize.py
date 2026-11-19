from pathlib import Path

import pytest

from pkostat.categorize.categorizer import Categorizer
from pkostat.categorize.config import (
    CATEGORIES_FILE,
    RULES_FILE,
    CategoryConfig,
    default_text,
    load_category_config,
)
from pkostat.categorize.merchants import generic_key
from pkostat.db.categories import StoredRule
from pkostat.domain import Kind, Source, Status, Transaction
from pkostat.errors import PkoStatError


@pytest.fixture(scope="module")
def config() -> CategoryConfig:
    return load_category_config()


def _tx(
    counterparty: str | None,
    kind: Kind = Kind.CARD,
    title: str | None = None,
    amount: int = -1000,
) -> Transaction:
    return Transaction(
        user_id=1,
        source=Source.CSV,
        source_id=7,
        occurred_on="2026-11-10",
        occurred_at=None,
        amount_minor=amount,
        currency="PLN",
        kind=kind,
        counterparty=counterparty,
        location=None,
        title=title,
        status=Status.SETTLED,
    )


def _categorize(
    config: CategoryConfig,
    tx: Transaction,
    stored: dict[str, StoredRule] | None = None,
    overrides: dict[tuple[str, int], str] | None = None,
) -> tuple[str | None, str | None]:
    categorizer = Categorizer(config, stored or {}, overrides or {})
    keyed = categorizer.with_merchant_key(tx)
    return keyed.merchant_key, categorizer.category_for(keyed)


@pytest.mark.parametrize(
    ("counterparty", "key", "category"),
    [
        ("WOLT", "WOLT", "Food delivery"),
        ("Wolt", "WOLT", "Food delivery"),
        ("Glovo 29SEP QYM1DUJSM", "GLOVO", "Food delivery"),
        ("UBER   *EATS", "UBER EATS", "Food delivery"),
        ("UBR* PENDING.UBER.COM", "UBER", "Taxi & scooters"),
        ("BOLT.EU/O/2611120000", "BOLT", "Taxi & scooters"),
        ("ZABKA Z8828 K.1", "ZABKA", "Convenience stores"),
        ("SKLEP ZAK 01", "ZAK", "Convenience stores"),
        ("allegro.pl", "ALLEGRO", "Household & pets"),
        ("PayPro SA *ALLEGRO", "ALLEGRO", "Household & pets"),
        ("store.steampowered.com", "STEAM", "Entertainment & games"),
        ("GOOGLE *YouTubePremium", "YOUTUBE PREMIUM", "Subscriptions & software"),
        ("LIDL DLUGA", "LIDL", "Groceries"),
        ("Apteka Pod Lipami 02", "APTEKA POD LIPAMI", "Health & pharmacy"),
        ("KAWIARNIA POD ZEGAREM", "KAWIARNIA POD ZEGAREM", "Restaurants & cafes"),
        ("820 IDREAM", "IDREAM", None),
    ],
)
def test_default_rules(
    config: CategoryConfig, counterparty: str, key: str, category: str | None
) -> None:
    assert _categorize(config, _tx(counterparty)) == (key, category)


@pytest.mark.parametrize(
    ("raw", "key"),
    [
        ("https://sportano.pl/", "SPORTANO"),
        ("www.leroymerlin.pl/", "LEROYMERLIN"),
        ("APPLE.COM/PL", "APPLE"),
        ("Escape Roomz P12345", "ESCAPE ROOMZ"),
        ('RESTAURACJAKOWAL" 3', "RESTAURACJAKOWAL"),
        ("12345", "12345"),
    ],
)
def test_generic_key(raw: str, key: str) -> None:
    assert generic_key(raw) == key


def test_defaults_by_kind(config: CategoryConfig) -> None:
    assert _categorize(config, _tx("UL. DLUGA 5", Kind.ATM))[1] == "Cash"
    assert _categorize(config, _tx("JANE DOE", Kind.TRANSFER_OUT))[1] == "Transfers to people"
    assert _categorize(config, _tx("JANE DOE", Kind.TRANSFER_IN, amount=500))[1] == (
        "Transfers from people"
    )


def test_salary_by_title(config: CategoryConfig) -> None:
    tx = _tx("ACME SP Z O.O.", Kind.TRANSFER_IN, "Wynagrodzenie za 10.2026", 900000)

    assert _categorize(config, tx)[1] == "Salary"


def test_title_rule_respects_kinds(config: CategoryConfig) -> None:
    # Paying someone with "wynagrodzenie" in the title is not income.
    tx = _tx("JANE DOE", Kind.TRANSFER_OUT, "wynagrodzenie dla Jane")

    assert _categorize(config, tx)[1] == "Transfers to people"


def test_refund_takes_merchant_category(config: CategoryConfig) -> None:
    assert _categorize(config, _tx("Pyszne.pl", Kind.REFUND, amount=4755))[1] == "Food delivery"


def test_precedence(config: CategoryConfig) -> None:
    rent = _tx("JANE LANDLORD", Kind.TRANSFER_OUT)
    manual = {"JANE LANDLORD": StoredRule("Rent & utilities", "manual")}
    llm_wolt = {"WOLT": StoredRule("Groceries", "llm")}
    llm_unknown = {"IDREAM": StoredRule("Electronics", "llm")}

    assert _categorize(config, rent, manual)[1] == "Rent & utilities"  # manual beats defaults
    assert _categorize(config, _tx("WOLT"), llm_wolt)[1] == "Food delivery"  # rules beat llm
    assert _categorize(config, _tx("820 IDREAM"), llm_unknown)[1] == "Electronics"
    override = {("csv", 7): "Groceries"}
    assert _categorize(config, _tx("WOLT"), manual, override)[1] == "Groceries"


def test_stale_stored_category_is_ignored(config: CategoryConfig) -> None:
    stored = {"IDREAM": StoredRule("Removed category", "manual")}

    assert _categorize(config, _tx("820 IDREAM"), stored)[1] is None


def test_user_files_win(tmp_path: Path) -> None:
    (tmp_path / CATEGORIES_FILE).write_text(
        '[[category]]\nname = "Food"\nkind = "impulse"\n', encoding="utf-8"
    )
    (tmp_path / RULES_FILE).write_text(
        '[[merchant]]\nmatch = "wolt"\ncategory = "Food"\n', encoding="utf-8"
    )

    config = load_category_config(tmp_path)

    assert list(config.categories) == ["Food"]
    assert _categorize(config, _tx("WOLT"))[1] == "Food"


@pytest.mark.parametrize(
    ("categories", "rules", "message"),
    [
        ('[[category]]\nname = "A"\nkind = "fun"\n', "", "kind"),
        ('[[category]]\nname = "A"\nkind = "other"\n' * 2, "", "listed twice"),
        ('[[category]]\nname = "A"\nkind = "other"\n', '[defaults]\natm = "B"\n', "unknown"),
        ('[[category]]\nname = "A"\nkind = "other"\n', '[[merchant]]\nmatch = "("\n', "pattern"),
        ('[[category]]\nname = "A"\nkind = "other"\n', '[[merchant]]\nmach = "x"\n', "mach"),
        (
            '[[category]]\nname = "A"\nkind = "other"\n',
            '[[merchant]]\nmatch = "x"\nalternative = "B"\n',
            "unknown",
        ),
        ("[[category]\n", "", "not valid TOML"),
    ],
)
def test_invalid_files_are_reported(
    tmp_path: Path, categories: str, rules: str, message: str
) -> None:
    (tmp_path / CATEGORIES_FILE).write_text(categories, encoding="utf-8")
    (tmp_path / RULES_FILE).write_text(rules, encoding="utf-8")

    with pytest.raises(PkoStatError, match=message):
        load_category_config(tmp_path)


def test_packaged_defaults_are_valid() -> None:
    assert "Food delivery" in load_category_config().categories
    assert "[defaults]" in default_text(RULES_FILE)
