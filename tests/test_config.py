from pathlib import Path

import pytest

from pkostat.config import DEFAULT_OLLAMA_MODEL, DEFAULT_OLLAMA_URL, load_settings
from pkostat.errors import PkoStatError


def test_defaults_without_env_file(tmp_path: Path) -> None:
    settings = load_settings({"PKOSTAT_HOME": str(tmp_path)})

    assert settings.home == tmp_path
    assert settings.db_path == tmp_path / "db" / "pkostat.db"
    assert settings.supabase_url is None
    assert settings.ollama_url == DEFAULT_OLLAMA_URL
    assert settings.ollama_model == DEFAULT_OLLAMA_MODEL


def test_reads_env_file_and_environment_wins(tmp_path: Path) -> None:
    (tmp_path / ".env").write_text(
        "SUPABASE_URL=https://file.supabase.co\nOLLAMA_MODEL=from-file\n", encoding="utf-8"
    )

    settings = load_settings({"PKOSTAT_HOME": str(tmp_path), "OLLAMA_MODEL": "from-env"})

    assert settings.supabase_url == "https://file.supabase.co"
    assert settings.ollama_model == "from-env"


def test_empty_values_count_as_missing(tmp_path: Path) -> None:
    (tmp_path / ".env").write_text("SUPABASE_URL=\nOLLAMA_URL=  \n", encoding="utf-8")

    settings = load_settings({"PKOSTAT_HOME": str(tmp_path)})

    assert settings.supabase_url is None
    assert settings.ollama_url == DEFAULT_OLLAMA_URL


def test_require_supabase_fails_with_hint(tmp_path: Path) -> None:
    settings = load_settings({"PKOSTAT_HOME": str(tmp_path)})

    with pytest.raises(PkoStatError, match="SUPABASE_SECRET_KEY"):
        settings.require_supabase()
