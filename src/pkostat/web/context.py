"""What every route needs: a database connection, the current category config, and a reply that
rebuilds transactions after a change."""

import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager

from fastapi.responses import JSONResponse

from pkostat.categorize.config import CategoryConfig, load_category_config
from pkostat.config import Settings
from pkostat.home import open_database
from pkostat.rebuild import rebuild


class Context:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def config(self) -> CategoryConfig:
        # Read on every request: the user may edit the TOML files while the app runs.
        return load_category_config(self.settings.home)

    @contextmanager
    def db(self) -> Iterator[sqlite3.Connection]:
        conn = open_database(self.settings)
        try:
            yield conn
        finally:
            conn.close()

    def done(self, conn: sqlite3.Connection, message: str) -> JSONResponse:
        """Every change can move a category or a month, so transactions are rebuilt before the
        browser reloads the page."""
        rebuild(conn, None, self.config())
        return JSONResponse({"ok": True, "message": message})


def category_blockers(conn: sqlite3.Connection, config: CategoryConfig, name: str) -> list[str]:
    """Why a category cannot be removed yet, in words; empty when it can."""
    reasons = []
    used = conn.execute("SELECT COUNT(*) FROM transactions WHERE category = ?", (name,)).fetchone()[
        0
    ]
    if used:
        reasons.append(f"операций: {used}")
    rules = conn.execute(
        "SELECT COUNT(*) FROM merchant_rules WHERE category = ?", (name,)
    ).fetchone()[0]
    if rules:
        reasons.append(f"правил мерчантов: {rules}")
    in_files = [r.category for r in config.merchant_rules] + [
        r.category for r in config.title_rules
    ]
    if name in in_files or name in config.defaults.model_dump().values():
        reasons.append("правила в rules.toml")
    return reasons
