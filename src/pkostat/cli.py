"""Command-line entry point: argument parsing only; handlers live in pkostat.commands."""

import argparse
import io
import logging
import sys
from collections.abc import Sequence

from pkostat.commands import categories, data, llm, maintenance, report, serve, users
from pkostat.errors import PkoStatError


def main(argv: Sequence[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if not argv:
        argv = ["serve"]  # plain `pkostat` opens the app
    # Merchant and person names contain Polish letters; a cp1252 pipe must not crash the command.
    for stream in (sys.stdout, sys.stderr):
        if isinstance(stream, io.TextIOWrapper):
            stream.reconfigure(errors="replace")
    args = _build_parser().parse_args(argv)
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.WARNING,
        format="%(levelname)s %(name)s: %(message)s",
    )
    try:
        return args.handler(args)
    except PkoStatError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="pkostat", description="PKO BP spending analyser.")
    parser.add_argument("-v", "--verbose", action="store_true", help="debug logging")
    sub = parser.add_subparsers(title="commands", required=True)

    serve_cmd = sub.add_parser("serve", help="the local admin website (default command)")
    serve_cmd.add_argument("--port", type=int, default=serve.DEFAULT_PORT)
    serve_cmd.add_argument("--no-browser", action="store_true", help="do not open the browser")
    serve_cmd.set_defaults(handler=serve.cmd_serve)

    init = sub.add_parser("init", help="create the data folder, .env template and database")
    init.set_defaults(handler=users.cmd_init)

    _add_user_commands(sub.add_parser("user", help="manage users and their tokens"))

    sync = sub.add_parser("sync", help="move notifications from Supabase into the local database")
    sync.set_defaults(handler=data.cmd_sync)

    import_csv = sub.add_parser("import-csv", help="import an iPKO CSV statement for a user")
    import_csv.add_argument("file", help="the exported 'Zestawienie operacji' .csv")
    import_csv.add_argument("--user", required=True)
    import_csv.set_defaults(handler=data.cmd_import_csv)

    rebuild = sub.add_parser("rebuild", help="rebuild transactions from stored raw data")
    rebuild.add_argument("--user", help="only this user (default: all)")
    rebuild.set_defaults(handler=data.cmd_rebuild)

    _add_category_commands(sub.add_parser("category", help="categories and merchant rules"))

    run_cmd = sub.add_parser("run", help="everything: sync, rebuild, LLM, reports, publish, backup")
    run_cmd.add_argument("--no-llm", action="store_true", help="skip the local LLM steps")
    run_cmd.set_defaults(handler=maintenance.cmd_run)

    publish = sub.add_parser("publish", help="push encrypted read-only reports to GitHub Pages")
    publish.add_argument("--force", action="store_true", help="push even if nothing changed")
    publish.set_defaults(handler=maintenance.cmd_publish)

    backup_cmd = sub.add_parser("backup", help="back up the database and config files")
    backup_cmd.add_argument("--list", action="store_true", help="list existing backups")
    backup_cmd.set_defaults(handler=maintenance.cmd_backup)

    restore_cmd = sub.add_parser("restore", help="restore a backup (close the app first)")
    restore_cmd.add_argument("file", help="a pkostat-*.zip from the backups folder")
    restore_cmd.set_defaults(handler=maintenance.cmd_restore)

    categorize = sub.add_parser(
        "categorize", help="local LLM suggests categories (confirm in the app)"
    )
    categorize.add_argument("--limit", type=int, help="ask about at most this many merchants")
    categorize.set_defaults(handler=llm.cmd_categorize)

    report_cmd = sub.add_parser("report", help="build the read-only report HTML for a user")
    report_cmd.add_argument("--user", required=True)
    report_cmd.add_argument(
        "--out", help="output file (default: PKOSTAT_HOME/reports/<user>/report.html)"
    )
    report_cmd.add_argument("--open", action="store_true", help="open it in the browser")
    report_cmd.set_defaults(handler=report.cmd_report)

    uncategorized = sub.add_parser("uncategorized", help="merchants without a category")
    uncategorized.add_argument("--user", help="only this user (default: all)")
    uncategorized.add_argument("--limit", type=int, default=40, help="rows to show (default 40)")
    uncategorized.set_defaults(handler=categories.cmd_uncategorized)
    return parser


def _add_category_commands(category: argparse.ArgumentParser) -> None:
    sub = category.add_subparsers(title="category commands", required=True)

    listing = sub.add_parser("list", help="categories from categories.toml")
    listing.set_defaults(handler=categories.cmd_category_list)

    assign = sub.add_parser("set", help="put every transaction of a merchant into a category")
    assign.add_argument("merchant", help="merchant as shown by `pkostat uncategorized`")
    assign.add_argument("category", help="category name or a unique prefix of it")
    assign.add_argument("--force", action="store_true", help="allow a merchant not seen yet")
    assign.set_defaults(handler=categories.cmd_category_set)

    unset = sub.add_parser("unset", help="remove a merchant rule set with `category set`")
    unset.add_argument("merchant")
    unset.set_defaults(handler=categories.cmd_category_unset)


def _add_user_commands(user: argparse.ArgumentParser) -> None:
    sub = user.add_subparsers(title="user commands", required=True)

    add = sub.add_parser("add", help="add a user and print their token")
    add.add_argument("name")
    add.add_argument("--token", help="register an existing token instead of generating one")
    add.add_argument("--display-name", help='name shown in reports, e.g. "Jane Doe"')
    add.set_defaults(handler=users.cmd_user_add)

    display = sub.add_parser("display-name", help='set the name shown in reports ("" clears it)')
    display.add_argument("name")
    display.add_argument("display_name", metavar="DISPLAY_NAME")
    display.set_defaults(handler=users.cmd_user_display_name)

    listing = sub.add_parser("list", help="list users, tokens and notification counts")
    listing.set_defaults(handler=users.cmd_user_list)

    rotate = sub.add_parser("rotate", help="replace a user's token")
    rotate.add_argument("name")
    rotate.set_defaults(handler=users.cmd_user_rotate)

    share = sub.add_parser("share", help="new link to the user's published report")
    share.add_argument("name")
    share.add_argument("--off", action="store_true", help="stop publishing the user's report")
    share.set_defaults(handler=users.cmd_user_share)
