"""Loading and validating categories.toml and rules.toml.

The user's copies in PKOSTAT_HOME win; without them the packaged defaults are used.
"""

import re
import tomllib
from enum import StrEnum
from functools import cached_property
from importlib.resources import files
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from pkostat.domain import Kind
from pkostat.errors import PkoStatError

CATEGORIES_FILE = "categories.toml"
RULES_FILE = "rules.toml"


class CategoryKind(StrEnum):
    ESSENTIAL = "essential"
    DISCRETIONARY = "discretionary"
    IMPULSE = "impulse"
    INCOME = "income"
    TRANSFER = "transfer"
    OTHER = "other"


class _Model(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class Category(_Model):
    name: str  # stable id: rules and stored choices reference it
    kind: CategoryKind
    description: str = ""
    label: str | None = None  # shown in the UI; falls back to name
    # Paid on or after this day of the month = belongs to the next month (rent paid on the 30th).
    month_shift_from_day: int | None = Field(default=None, ge=2, le=31)

    @property
    def display(self) -> str:
        return self.label or self.name


class _Rule(_Model):
    match: str
    kinds: list[Kind] | None = None

    @cached_property
    def pattern(self) -> re.Pattern[str]:
        return re.compile(self.match, re.IGNORECASE)

    def applies(self, kind: Kind, text: str | None) -> bool:
        if self.kinds is not None and kind not in self.kinds:
            return False
        return text is not None and self.pattern.search(text) is not None


class MerchantRule(_Rule):
    key: str | None = None
    category: str | None = None
    # A second category this merchant often belongs to (Wolt: food or groceries). The bank data
    # cannot tell them apart, so the app offers a one-tap switch per operation.
    alternative: str | None = None


class TitleRule(_Rule):
    category: str


class Defaults(_Model):
    atm: str | None = None
    transfer_in: str | None = None
    transfer_out: str | None = None


class _CategoriesFile(_Model):
    category: list[Category]


class _RulesFile(_Model):
    defaults: Defaults = Defaults()
    title: list[TitleRule] = []
    merchant: list[MerchantRule] = []


class CategoryConfig(_Model):
    categories: dict[str, Category]
    defaults: Defaults
    title_rules: list[TitleRule]
    merchant_rules: list[MerchantRule]


def load_category_config(home: Path | None = None) -> CategoryConfig:
    categories = _parse(_CategoriesFile, _source(home, CATEGORIES_FILE), CATEGORIES_FILE)
    rules = _parse(_RulesFile, _source(home, RULES_FILE), RULES_FILE)
    by_name: dict[str, Category] = {}
    for category in categories.category:
        if category.name in by_name:
            raise PkoStatError(f"{CATEGORIES_FILE}: category {category.name!r} is listed twice.")
        by_name[category.name] = category
    config = CategoryConfig(
        categories=by_name,
        defaults=rules.defaults,
        title_rules=rules.title,
        merchant_rules=rules.merchant,
    )
    _check_rules(config)
    return config


def default_text(name: str) -> str:
    return files("pkostat.categorize").joinpath("defaults", name).read_text("utf-8")


def _source(home: Path | None, name: str) -> str:
    user_file = None if home is None else home / name
    if user_file is not None and user_file.is_file():
        return user_file.read_text("utf-8")
    return default_text(name)


def _parse[T: BaseModel](model: type[T], text: str, name: str) -> T:
    try:
        return model.model_validate(tomllib.loads(text))
    except tomllib.TOMLDecodeError as exc:
        raise PkoStatError(f"{name}: not valid TOML: {exc}") from exc
    except ValidationError as exc:
        raise PkoStatError(f"{name}: {exc}") from exc


def _check_rules(config: CategoryConfig) -> None:
    named = [
        *(("defaults", value) for value in config.defaults.model_dump().values() if value),
        *(("title rule", rule.category) for rule in config.title_rules),
        *(("merchant rule", rule.category) for rule in config.merchant_rules if rule.category),
        *(("alternative", r.alternative) for r in config.merchant_rules if r.alternative),
    ]
    unknown = sorted({name for _, name in named if name not in config.categories})
    if unknown:
        raise PkoStatError(f"{RULES_FILE}: unknown categories {unknown}; see {CATEGORIES_FILE}.")
    for rule in [*config.title_rules, *config.merchant_rules]:
        try:
            _ = rule.pattern
        except re.error as exc:
            raise PkoStatError(f"{RULES_FILE}: bad pattern {rule.match!r}: {exc}") from exc
