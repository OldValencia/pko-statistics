from pathlib import Path

import pytest
from statement_data import CARD, PENDING, write_statement

from pkostat.cli import main

UUID_TOKEN = "00000000-1111-4222-8333-444444444444"


def test_init_creates_layout(home: Path, capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["init"]) == 0

    assert (home / "db" / "pkostat.db").is_file()
    assert (home / ".env").is_file()
    assert (home / "reports").is_dir()
    assert (home / "backups").is_dir()
    assert "001_initial.sql" in capsys.readouterr().out


def test_init_twice_keeps_env_and_applies_nothing(
    home: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    main(["init"])
    (home / ".env").write_text("SUPABASE_URL=https://mine.supabase.co\n", encoding="utf-8")
    capsys.readouterr()

    assert main(["init"]) == 0

    assert "mine.supabase.co" in (home / ".env").read_text(encoding="utf-8")
    out = capsys.readouterr().out
    assert "Applied migrations" not in out
    assert "Created" not in out


def test_commands_need_init_first(home: Path, capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["user", "list"]) == 1

    assert "pkostat init" in capsys.readouterr().err


def test_user_add_and_list(home: Path, capsys: pytest.CaptureFixture[str]) -> None:
    main(["init"])

    assert main(["user", "add", "alice", "--token", UUID_TOKEN]) == 0
    assert main(["user", "list"]) == 0

    out = capsys.readouterr().out
    assert "Added user 'alice'" in out
    assert "alice (alice)  notifications=0" in out
    assert UUID_TOKEN in out


def test_user_add_duplicate_fails(home: Path, capsys: pytest.CaptureFixture[str]) -> None:
    main(["init"])
    main(["user", "add", "alice"])

    assert main(["user", "add", "alice"]) == 1

    assert "already exists" in capsys.readouterr().err


def test_sync_without_supabase_settings(home: Path, capsys: pytest.CaptureFixture[str]) -> None:
    main(["init"])

    assert main(["sync"]) == 1

    assert "SUPABASE_SECRET_KEY" in capsys.readouterr().err


def test_display_name_commands(home: Path, capsys: pytest.CaptureFixture[str]) -> None:
    main(["init"])

    assert main(["user", "add", "jane", "--display-name", "Jane D"]) == 0
    assert main(["user", "display-name", "jane", "Jane Doe"]) == 0
    assert main(["user", "list"]) == 0

    out = capsys.readouterr().out
    assert "Added user 'jane' (Jane D)" in out
    assert "jane (Jane Doe)" in out


def test_rebuild_command(home: Path, capsys: pytest.CaptureFixture[str]) -> None:
    main(["init"])

    assert main(["rebuild"]) == 0
    assert main(["rebuild", "--user", "ghost"]) == 1

    captured = capsys.readouterr()
    assert "Statement transactions: 0" in captured.out
    assert "No user 'ghost'" in captured.err


def test_import_csv_command(home: Path, capsys: pytest.CaptureFixture[str]) -> None:
    main(["init"])
    main(["user", "add", "alice"])
    path = write_statement(home / "s 01.11.2026 - 12.11.2026.csv", [PENDING, CARD])

    assert main(["import-csv", str(path), "--user", "alice"]) == 0
    assert main(["import-csv", str(path), "--user", "alice"]) == 0

    out = capsys.readouterr().out
    assert "2 new rows, 0 already stored; the file has 1 pending holds" in out
    assert "imported before" in out
    assert "0 new rows, 2 already stored" in out
    assert "Statement transactions: 2." in out
    assert "Holds: 1 (pending 1" in out


def _cli_with_statement(home: Path) -> None:
    main(["init"])
    main(["user", "add", "alice"])
    rows = [CARD, ["2026-11-05", "2026-11-05", "Przelew z rachunku", "-1500.00", "PLN", "+10.00",
                   "Nazwa odbiorcy: JANE LANDLORD", "Tytuł: CZYNSZ 11.2026"]]  # fmt: skip
    main(["import-csv", str(write_statement(home / "s.csv", rows)), "--user", "alice"])


def test_init_creates_editable_configs(home: Path) -> None:
    main(["init"])

    assert "[[category]]" in (home / "categories.toml").read_text(encoding="utf-8")
    assert "[defaults]" in (home / "rules.toml").read_text(encoding="utf-8")


def test_category_set_and_unset(home: Path, capsys: pytest.CaptureFixture[str]) -> None:
    _cli_with_statement(home)
    capsys.readouterr()

    assert main(["category", "set", "JANE LANDLORD", "rent"]) == 0
    assert "JANE LANDLORD -> Rent & utilities" in capsys.readouterr().out
    assert main(["category", "unset", "JANE LANDLORD"]) == 0
    assert main(["category", "unset", "JANE LANDLORD"]) == 1


def test_category_set_validates(home: Path, capsys: pytest.CaptureFixture[str]) -> None:
    _cli_with_statement(home)

    assert main(["category", "set", "NOBODY", "Groceries"]) == 1
    assert main(["category", "set", "NOBODY", "Groceries", "--force"]) == 0
    assert main(["category", "set", "WOLT", "nonsense"]) == 1
    assert main(["category", "set", "WOLT", "s"]) == 1  # ambiguous: Salary, Sport, Subscriptions

    err = capsys.readouterr().err
    assert "No transactions with merchant 'NOBODY'" in err
    assert "Unknown category 'nonsense'" in err
    assert "matches" in err


def test_uncategorized_and_list(home: Path, capsys: pytest.CaptureFixture[str]) -> None:
    _cli_with_statement(home)
    main(["category", "set", "JANE LANDLORD", "Rent & utilities"])
    capsys.readouterr()

    assert main(["uncategorized"]) == 0
    assert "Everything is categorised." in capsys.readouterr().out
    assert main(["category", "list"]) == 0
    assert "Food delivery" in capsys.readouterr().out


def test_report_command(home: Path, capsys: pytest.CaptureFixture[str]) -> None:
    _cli_with_statement(home)
    capsys.readouterr()

    assert main(["report", "--user", "alice"]) == 0

    out = home / "reports" / "alice" / "report.html"
    assert out.is_file()
    assert "user-mode" in out.read_text(encoding="utf-8")
    assert "Report:" in capsys.readouterr().out
