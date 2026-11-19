"""`init` and `user …` commands."""

import argparse
from contextlib import closing

from pkostat.config import load_settings
from pkostat.db.notifications import notification_counts_by_user
from pkostat.db.users import list_users
from pkostat.home import init_home, open_database
from pkostat.publish.sharing import close_share, open_share, share_link
from pkostat.users import add_user, rotate_token, set_display_name


def cmd_init(args: argparse.Namespace) -> int:
    settings = load_settings()
    result = init_home(settings)
    print(f"Data folder: {settings.home}")
    if result.created_env:
        print(f"Created {settings.env_path}: fill in the Supabase settings.")
    for name in result.created_configs:
        print(f"Created {settings.home / name}: edit it to your taste.")
    if result.applied_migrations:
        print(f"Applied migrations: {', '.join(result.applied_migrations)}")
    print(f"Database: {settings.db_path} (schema version {result.schema_version})")
    return 0


def cmd_user_add(args: argparse.Namespace) -> int:
    with closing(open_database(load_settings())) as conn:
        user = add_user(conn, args.name, args.token, args.display_name)
    print(f"Added user '{user.name}' ({user.label}).")
    if args.token is None:
        print(f"Token: {user.token}")
        print("Put it into the iOS Shortcut as token_id.")
    return 0


def cmd_user_list(args: argparse.Namespace) -> int:
    with closing(open_database(load_settings())) as conn:
        users = list_users(conn)
        counts = notification_counts_by_user(conn)
    if not users:
        print("No users. Add one with `pkostat user add <name>`.")
        return 0
    for user in users:
        print(
            f"{user.name} ({user.label})  notifications={counts.get(user.id, 0)}  "
            f"since={user.created_at}"
        )
        print(f"    token: {user.token}")
    return 0


def cmd_user_display_name(args: argparse.Namespace) -> int:
    with closing(open_database(load_settings())) as conn:
        user = set_display_name(conn, args.name, args.display_name)
    print(f"'{user.name}' is shown as: {user.label}")
    return 0


def cmd_user_rotate(args: argparse.Namespace) -> int:
    with closing(open_database(load_settings())) as conn:
        user = rotate_token(conn, args.name)
    print(f"New token for '{user.name}': {user.token}")
    print("Update the iOS Shortcut: pushes with the old token will be rejected from now on.")
    return 0


def cmd_user_share(args: argparse.Namespace) -> int:
    settings = load_settings()
    with closing(open_database(settings)) as conn:
        if args.off:
            user = close_share(conn, args.name)
            print(f"'{user.name}': report no longer shared; it disappears on the next publish.")
            return 0
        user = open_share(conn, args.name)
    link = share_link(settings, user)
    print(f"New link for '{user.name}' (the old one stops working on the next publish):")
    print(f"    {link or 'set PKOSTAT_PUBLISH_REMOTE (or PKOSTAT_PUBLISH_URL) in .env first'}")
    print("Run `pkostat publish` to put it online.")
    return 0
