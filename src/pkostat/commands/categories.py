"""`category …` and `uncategorized` commands."""

import argparse
from contextlib import closing

from pkostat.categorize.config import CategoryConfig, load_category_config
from pkostat.clock import now_local_iso
from pkostat.commands.data import print_rebuild
from pkostat.config import load_settings
from pkostat.db.categories import delete_rule, known_merchant_keys, set_rule
from pkostat.db.transactions import uncategorised_merchants
from pkostat.errors import PkoStatError
from pkostat.home import open_database
from pkostat.money import format_amount
from pkostat.rebuild import rebuild
from pkostat.users import get_user


def cmd_category_list(args: argparse.Namespace) -> int:
    config = load_category_config(load_settings().home)
    width = max(len(name) for name in config.categories)
    for category in config.categories.values():
        print(f"{category.name:<{width}}  {category.kind:<13}  {category.description}")
    return 0


def cmd_category_set(args: argparse.Namespace) -> int:
    settings = load_settings()
    config = load_category_config(settings.home)
    category = _resolve(config, args.category)
    with closing(open_database(settings)) as conn:
        if args.merchant not in known_merchant_keys(conn) and not args.force:
            raise PkoStatError(
                f"No transactions with merchant {args.merchant!r}. Names come from "
                "`pkostat uncategorized`; use --force to add a rule for a future merchant."
            )
        with conn:
            set_rule(conn, args.merchant, category, "manual", now_local_iso())
        result = rebuild(conn, None, config)
    print(f"{args.merchant} -> {category}")
    print_rebuild(result)
    return 0


def cmd_category_unset(args: argparse.Namespace) -> int:
    settings = load_settings()
    config = load_category_config(settings.home)
    with closing(open_database(settings)) as conn:
        with conn:
            removed = delete_rule(conn, args.merchant)
        if not removed:
            raise PkoStatError(f"No stored rule for merchant {args.merchant!r}.")
        result = rebuild(conn, None, config)
    print(f"Removed the rule for {args.merchant}.")
    print_rebuild(result)
    return 0


def cmd_uncategorized(args: argparse.Namespace) -> int:
    with closing(open_database(load_settings())) as conn:
        user_id = None if args.user is None else get_user(conn, args.user).id
        merchants = uncategorised_merchants(conn, user_id, args.limit)
    if not merchants:
        print("Everything is categorised.")
        return 0
    print(f"{'total PLN':>12}  {'count':>5}  merchant  (as the bank spells it)")
    for merchant in merchants:
        print(
            f"{format_amount(merchant.total_minor):>12}  {merchant.count:>5}  "
            f"{merchant.merchant_key}  ({merchant.example})"
        )
    print('Assign with: pkostat category set "<merchant>" "<category>"')
    return 0


def _resolve(config: CategoryConfig, name: str) -> str:
    """Exact name, or a case-insensitive unique prefix: 'food' -> 'Food delivery'."""
    if name in config.categories:
        return name
    matches = [known for known in config.categories if known.lower().startswith(name.lower())]
    if len(matches) == 1:
        return matches[0]
    hint = f"matches {matches}" if matches else "see `pkostat category list`"
    raise PkoStatError(f"Unknown category {name!r}: {hint}.")
