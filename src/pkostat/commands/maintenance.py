"""`run`, `backup` and `restore` commands."""

import argparse
from contextlib import closing
from pathlib import Path

from pkostat.backup import create_backup, list_backups, restore_backup
from pkostat.config import load_settings
from pkostat.home import open_database
from pkostat.pipeline import run_all
from pkostat.publish.service import publish_reports


def cmd_run(args: argparse.Namespace) -> int:
    steps = run_all(load_settings(), use_llm=not args.no_llm)
    for step in steps:
        print(f"[{'ok' if step.ok else 'FAIL'}] {step.name}: {step.message}")
    return 0 if all(step.ok for step in steps) else 1


def cmd_publish(args: argparse.Namespace) -> int:
    settings = load_settings()
    with closing(open_database(settings)) as conn:
        result = publish_reports(conn, settings, force=args.force)
    if not result.changed:
        print(f"Nothing changed since {result.published_at}; not pushed (use --force).")
    else:
        print(f"Published {result.reports} report(s) at {result.published_at}.")
    return 0


def cmd_backup(args: argparse.Namespace) -> int:
    settings = load_settings()
    if args.list:
        backups = list_backups(settings)
        for info in backups:
            print(f"{info.created:%Y-%m-%d %H:%M}  {info.size // 1024:>6} KB  {info.path}")
        if not backups:
            print(f"No backups in {settings.backups_dir}.")
        return 0
    print(f"Backup: {create_backup(settings)}")
    return 0


def cmd_restore(args: argparse.Namespace) -> int:
    settings = load_settings()
    safety = restore_backup(settings, Path(args.file))
    print(f"Restored from {args.file}. The previous state is saved as {safety}.")
    print("Close the app if it was running and start it again.")
    return 0
