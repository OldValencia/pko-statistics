from pathlib import Path

import pytest
from statement_data import CARD, PHONE_OUT, write_statement

from pkostat import pipeline
from pkostat.cli import main
from pkostat.config import load_settings
from pkostat.errors import PkoStatError


class OllamaOff:
    def __init__(self, *args: object, **kwargs: object) -> None:
        raise PkoStatError("Ollama is not running at http://127.0.0.1:11434: start Ollama.")


@pytest.fixture
def ready(home: Path) -> Path:
    main(["init"])
    main(["user", "add", "alice"])
    statement = write_statement(home / "s 01.11.2026 - 12.11.2026.csv", [CARD, PHONE_OUT])
    main(["import-csv", str(statement), "--user", "alice"])
    return home


def test_failed_steps_do_not_stop_the_rest(ready: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(pipeline, "OllamaClient", OllamaOff)

    steps = pipeline.run_all(load_settings())

    result = {step.name: step.ok for step in steps}
    assert result == {
        "Синхронизация": True,  # skipped without Supabase, which is fine
        "Пересборка": True,
        "LLM: подсказки категорий": False,
        "Отчёты": True,
        "Публикация": True,  # skipped: not configured
        "Резервная копия": True,
    }
    assert "пропущено" in steps[0].message
    assert (ready / "reports" / "alice" / "report.html").is_file()
    assert list((ready / "backups").glob("pkostat-*.zip"))


def test_without_llm(ready: Path, capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["run", "--no-llm"]) == 0

    out = capsys.readouterr().out
    assert "LLM" not in out
    assert "[ok] Резервная копия" in out


def test_run_exit_code_reports_failures(ready: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(pipeline, "OllamaClient", OllamaOff)

    assert main(["run"]) == 1
