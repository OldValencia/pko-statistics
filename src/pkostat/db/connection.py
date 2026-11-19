import sqlite3
from pathlib import Path

MEMORY = ":memory:"


def connect(path: Path | str) -> sqlite3.Connection:
    if str(path) != MEMORY:
        Path(path).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    # Off by default in SQLite; without it REFERENCES clauses are decorative.
    conn.execute("PRAGMA foreign_keys = ON")
    return conn
