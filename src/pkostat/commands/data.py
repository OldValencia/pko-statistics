"""`sync`, `import-csv` and `rebuild` commands."""

import argparse
from contextlib import closing
from pathlib import Path

from pkostat.categorize.config import load_category_config
from pkostat.config import load_settings
from pkostat.domain import Status
from pkostat.home import open_database
from pkostat.ingest.supabase import SupabaseInbox
from pkostat.ingest.sync import sync_inbox
from pkostat.money import format_amount
from pkostat.rebuild import RebuildResult, rebuild
from pkostat.statement_import import import_statement
from pkostat.users import get_user


def cmd_sync(args: argparse.Namespace) -> int:
    settings = load_settings()
    url, key = settings.require_supabase()
    with closing(open_database(settings)) as conn, SupabaseInbox(url, key) as inbox:
        result = sync_inbox(conn, inbox)
    print(
        f"Stored {result.stored} new notifications, skipped {result.duplicates} already stored, "
        f"rejected {result.rejected}."
    )
    if result.rejected:
        print("Rejected = unknown token_id; kept in the rejected_notifications table.")
    return 0


def cmd_import_csv(args: argparse.Namespace) -> int:
    settings = load_settings()
    config = load_category_config(settings.home)
    with closing(open_database(settings)) as conn:
        user = get_user(conn, args.user)
        imported = import_statement(conn, user, Path(args.file))
        result = rebuild(conn, user.id, config)
    if imported.imported_before:
        print(f"This file was imported before ({imported.imported_before}); adding missing rows.")
    print(
        f"Imported {imported.file_name} ({imported.period_from} .. {imported.period_to}): "
        f"{imported.new_rows} new rows, {imported.known_rows} already stored; "
        f"the file has {imported.pending_rows} pending holds."
    )
    print_rebuild(result)
    return 0


def cmd_rebuild(args: argparse.Namespace) -> int:
    settings = load_settings()
    config = load_category_config(settings.home)
    with closing(open_database(settings)) as conn:
        user_id = None if args.user is None else get_user(conn, args.user).id
        result = rebuild(conn, user_id, config)
    print_rebuild(result)
    return 0


def print_rebuild(result: RebuildResult) -> None:
    pushes, holds = result.pushes, result.holds
    print(f"Statement transactions: {result.statement_rows}.")
    if holds:
        print(
            f"Holds: {holds.total()} (pending {holds[Status.PENDING]}, "
            f"booked since {holds[Status.SUPERSEDED]}, never booked {holds[Status.UNMATCHED]})."
        )
    print(
        f"Push transactions: {pushes.total()} (pending {pushes[Status.PENDING]}, "
        f"matched to statement {pushes[Status.SUPERSEDED]}, unmatched {pushes[Status.UNMATCHED]})."
    )
    if result.duplicate_pushes:
        print(f"Re-sent copies of the same push, ignored: {result.duplicate_pushes}.")
    if result.unparsed:
        print(f"Unrecognised notifications: {result.unparsed}.")
        for header, count in result.unparsed_headers.most_common():
            print(f"    {count} x {header!r}")
    if result.statement_errors:
        print(f"Statement rows that no longer parse: {result.statement_errors}.")
    print(
        f"Categorised: {result.counted - result.uncategorised} of {result.counted}; "
        f"uncategorised {result.uncategorised} ({format_amount(result.uncategorised_minor)} PLN). "
        "See `pkostat uncategorized`."
    )
