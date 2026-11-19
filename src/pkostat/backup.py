"""Backups: after sync a push exists only on this disk, so the database is copied regularly.

A backup is one zip: a consistent snapshot of the database (SQLite backup API, safe while the
app runs) plus categories.toml and rules.toml. Never .env: the folder may be a cloud drive and
.env holds the Supabase secret key.
"""

import shutil
import sqlite3
import tempfile
import zipfile
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path

from pkostat.categorize.config import CATEGORIES_FILE, RULES_FILE
from pkostat.clock import WARSAW
from pkostat.config import Settings
from pkostat.db.migrate import load_migrations
from pkostat.errors import PkoStatError

DB_NAME = "pkostat.db"
PREFIX = "pkostat-"
KEEP = 30


@dataclass(frozen=True, slots=True)
class BackupInfo:
    path: Path
    created: datetime
    size: int


def create_backup(settings: Settings, keep: int = KEEP) -> Path:
    if not settings.db_path.is_file():
        raise PkoStatError("Nothing to back up yet: run `pkostat init` first.")
    folder = settings.backups_dir
    folder.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(WARSAW).strftime("%Y-%m-%d_%H%M%S")
    target = folder / f"{PREFIX}{stamp}.zip"
    # Two backups in one second (the daily one at start-up and a button press) must not
    # overwrite each other.
    copy_number = 1
    while target.exists():
        copy_number += 1
        target = folder / f"{PREFIX}{stamp}-{copy_number}.zip"
    with tempfile.TemporaryDirectory() as tmp:
        snapshot = Path(tmp) / DB_NAME
        source, copy = sqlite3.connect(settings.db_path), sqlite3.connect(snapshot)
        try:
            source.backup(copy)
        finally:
            copy.close()
            source.close()
        partial = target.with_suffix(".zip.partial")
        with zipfile.ZipFile(partial, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            archive.write(snapshot, DB_NAME)
            for name in (CATEGORIES_FILE, RULES_FILE):
                if (settings.home / name).is_file():
                    archive.write(settings.home / name, name)
        partial.replace(target)
    prune(settings, keep)
    return target


def list_backups(settings: Settings) -> list[BackupInfo]:
    folder = settings.backups_dir
    found = []
    for path in folder.glob(f"{PREFIX}*.zip") if folder.is_dir() else []:
        stamp = path.stem.removeprefix(PREFIX)[:17]  # without a "-2" suffix
        try:
            created = datetime.strptime(stamp, "%Y-%m-%d_%H%M%S").replace(tzinfo=WARSAW)
        except ValueError:
            continue
        found.append(BackupInfo(path, created, path.stat().st_size))
    return sorted(found, key=lambda info: (info.created, info.path.name), reverse=True)


def prune(settings: Settings, keep: int = KEEP) -> list[Path]:
    old = [info.path for info in list_backups(settings)[keep:]]
    for path in old:
        path.unlink()
    return old


def backup_if_due(settings: Settings, max_age: timedelta = timedelta(days=1)) -> Path | None:
    latest = next(iter(list_backups(settings)), None)
    if latest and datetime.now(WARSAW) - latest.created < max_age:
        return None
    return create_backup(settings)


def restore_backup(settings: Settings, archive_path: Path) -> Path:
    """Check the backup, keep the current state as one more backup, then replace. The app must
    not be running: an open database cannot be swapped underneath it on Windows."""
    if not archive_path.is_file():
        raise PkoStatError(f"No such file: {archive_path}")
    with tempfile.TemporaryDirectory() as tmp:
        with zipfile.ZipFile(archive_path) as archive:
            if DB_NAME not in archive.namelist():
                raise PkoStatError(f"{archive_path.name} is not a PkoStat backup.")
            archive.extractall(tmp)
        restored = Path(tmp) / DB_NAME
        _check(restored)
        safety = create_backup(settings, keep=KEEP + 1) if settings.db_path.is_file() else None
        settings.db_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(restored, settings.db_path)
        for name in (CATEGORIES_FILE, RULES_FILE):
            if (Path(tmp) / name).is_file():
                shutil.copyfile(Path(tmp) / name, settings.home / name)
    return safety or archive_path


def _check(db: Path) -> None:
    conn = sqlite3.connect(db)
    try:
        verdict = conn.execute("PRAGMA integrity_check").fetchone()[0]
        version = conn.execute("PRAGMA user_version").fetchone()[0]
    except sqlite3.DatabaseError as exc:
        raise PkoStatError(f"The backup's database cannot be read: {exc}") from exc
    finally:
        conn.close()
    if verdict != "ok":
        raise PkoStatError(f"The backup is damaged: {verdict}")
    if version > len(load_migrations()):
        raise PkoStatError("The backup was made by a newer PkoStat. Update PkoStat first.")
