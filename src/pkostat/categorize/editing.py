"""Changing categories from the app and writing categories.toml back.

A category's `name` never changes once created: rules.toml, stored merchant rules and overrides
point at it. What the user "renames" is the label.
"""

import json
from pathlib import Path

from pkostat.categorize.config import CATEGORIES_FILE, Category, CategoryConfig, CategoryKind
from pkostat.errors import PkoStatError

HEADER = """\
# PkoStat categories. Edited from the app (Categories page) or by hand; then rebuild.
#
# name:  the id rules and stored choices refer to; do not change it by hand.
# label: the name shown in the app.
# kind:  essential | discretionary | impulse | income | transfer | other
# month_shift_from_day: paid on or after this day = counted in the next month.
# description: what belongs here; the local LLM reads it when it sorts unknown merchants.
"""


def update_category(
    config: CategoryConfig,
    name: str,
    label: str,
    kind: str,
    description: str,
    month_shift_from_day: int | None,
) -> list[Category]:
    if name not in config.categories:
        raise PkoStatError(f"Unknown category {name!r}.")
    changed = _validated(name, label, kind, description, month_shift_from_day)
    return [changed if c.name == name else c for c in config.categories.values()]


def add_category(config: CategoryConfig, label: str, kind: str, description: str) -> list[Category]:
    label = " ".join(label.split())
    taken = {c.name.lower() for c in config.categories.values()} | {
        c.display.lower() for c in config.categories.values()
    }
    if label.lower() in taken:
        raise PkoStatError(f"Category {label!r} already exists.")
    return [*config.categories.values(), _validated(label, label, kind, description, None)]


def remove_category(config: CategoryConfig, name: str, used_by: list[str]) -> list[Category]:
    if name not in config.categories:
        raise PkoStatError(f"Unknown category {name!r}.")
    if used_by:
        raise PkoStatError(f"Category is still used: {', '.join(used_by)}.")
    return [c for c in config.categories.values() if c.name != name]


def save_categories(home: Path, categories: list[Category]) -> None:
    blocks = [HEADER]
    for category in categories:
        lines = ["[[category]]", f"name = {_toml(category.name)}"]
        if category.label:
            lines.append(f"label = {_toml(category.label)}")
        if category.month_shift_from_day:
            lines.append(f"month_shift_from_day = {category.month_shift_from_day}")
        lines.append(f"kind = {_toml(category.kind.value)}")
        lines.append(f"description = {_toml(category.description)}")
        blocks.append("\n".join(lines) + "\n")
    path = home / CATEGORIES_FILE
    temporary = path.with_suffix(".toml.tmp")
    temporary.write_text("\n".join(blocks), encoding="utf-8", newline="\n")
    temporary.replace(path)


def _validated(
    name: str, label: str, kind: str, description: str, month_shift_from_day: int | None
) -> Category:
    label = " ".join(label.split())
    if not label or len(label) > 60:
        raise PkoStatError("A category label must be 1-60 characters.")
    if kind not in {k.value for k in CategoryKind}:
        raise PkoStatError(f"Unknown kind {kind!r}.")
    if month_shift_from_day is not None and not 2 <= month_shift_from_day <= 31:
        raise PkoStatError("The month shift day must be between 2 and 31.")
    return Category(
        name=name,
        label=label,
        kind=CategoryKind(kind),
        description=" ".join(description.split())[:300],
        month_shift_from_day=month_shift_from_day,
    )


def _toml(value: str) -> str:
    # A JSON string is a valid TOML basic string: same quotes and escapes.
    return json.dumps(value, ensure_ascii=False)
