import sqlite3
import zipfile
from datetime import timedelta
from pathlib import Path

import pytest

from pkostat import backup
from pkostat.cli import main
from pkostat.config import load_settings
from pkostat.errors import PkoStatError


@pytest.fixture
def settings(home: Path, monkeypatch: pytest.MonkeyPatch):
    main(["init"])
    main(["user", "add", "alice"])
    (home / ".env").write_text("SUPABASE_SECRET_KEY=very-secret\n", encoding="utf-8")
    return load_settings()


def _users(home: Path) -> list[str]:
    with sqlite3.connect(home / "db" / "pkostat.db") as conn:
        return [row[0] for row in conn.execute("SELECT name FROM users ORDER BY name")]


def test_backup_contains_db_and_configs_but_no_secrets(settings, home: Path) -> None:
    path = backup.create_backup(settings)

    with zipfile.ZipFile(path) as archive:
        assert sorted(archive.namelist()) == ["categories.toml", "pkostat.db", "rules.toml"]
        assert b"very-secret" not in b"".join(archive.read(n) for n in archive.namelist())
    assert path.parent == home / "backups"


def test_backup_folder_from_environment(
    home: Path, monkeypatch: pytest.MonkeyPatch, tmp_path_factory
) -> None:
    main(["init"])
    elsewhere = tmp_path_factory.mktemp("cloud")
    monkeypatch.setenv("PKOSTAT_BACKUP_DIR", str(elsewhere))

    assert backup.create_backup(load_settings()).parent == elsewhere


def test_old_backups_are_pruned(settings) -> None:
    for day in range(1, 6):
        (settings.backups_dir / f"pkostat-2026-01-0{day}_120000.zip").write_bytes(b"x")

    removed = backup.prune(settings, keep=2)

    assert [p.name[8:18] for p in removed] == ["2026-01-03", "2026-01-02", "2026-01-01"]
    assert len(backup.list_backups(settings)) == 2


def test_backup_if_due(settings) -> None:
    assert backup.backup_if_due(settings) is not None
    assert backup.backup_if_due(settings) is None
    assert backup.backup_if_due(settings, max_age=timedelta(0)) is not None


def test_restore_round_trip(settings, home: Path) -> None:
    saved = backup.create_backup(settings)
    main(["user", "add", "bob"])
    assert _users(home) == ["alice", "bob"]

    safety = backup.restore_backup(settings, saved)

    assert _users(home) == ["alice"]
    assert safety != saved and safety.is_file()  # the state with bob is kept
    backup.restore_backup(settings, safety)
    assert _users(home) == ["alice", "bob"]


def test_restore_refuses_foreign_or_broken_files(settings, home: Path) -> None:
    foreign = home / "photos.zip"
    with zipfile.ZipFile(foreign, "w") as archive:
        archive.writestr("cat.jpg", b"meow")
    broken = home / "pkostat-broken.zip"
    with zipfile.ZipFile(broken, "w") as archive:
        archive.writestr("pkostat.db", b"not a database at all" * 100)

    with pytest.raises(PkoStatError, match="not a PkoStat backup"):
        backup.restore_backup(settings, foreign)
    with pytest.raises(PkoStatError, match="cannot be read"):
        backup.restore_backup(settings, broken)
    assert _users(home) == ["alice"]  # untouched


def test_cli_backup_and_list(settings, capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["backup"]) == 0
    assert main(["backup", "--list"]) == 0

    out = capsys.readouterr().out
    assert "Backup:" in out and "KB" in out


def test_two_backups_in_one_second_both_survive(settings) -> None:
    first, second = backup.create_backup(settings), backup.create_backup(settings)

    assert first != second and first.is_file() and second.is_file()
