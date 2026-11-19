import sqlite3
from collections.abc import Iterator
from pathlib import Path

import pytest

from pkostat.db.connection import MEMORY, connect
from pkostat.db.migrate import migrate


@pytest.fixture
def db() -> Iterator[sqlite3.Connection]:
    """In-memory database with the full schema."""
    conn = connect(MEMORY)
    migrate(conn)
    yield conn
    conn.close()


@pytest.fixture
def home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """An empty PKOSTAT_HOME; Supabase and publish settings from the real environment are hidden."""
    monkeypatch.setenv("PKOSTAT_HOME", str(tmp_path))
    monkeypatch.delenv("SUPABASE_URL", raising=False)
    monkeypatch.delenv("SUPABASE_SECRET_KEY", raising=False)
    monkeypatch.delenv("PKOSTAT_PUBLISH_REMOTE", raising=False)
    monkeypatch.delenv("PKOSTAT_PUBLISH_URL", raising=False)
    return tmp_path
