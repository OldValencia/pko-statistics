"""Settings read from PKOSTAT_HOME/.env, overridden by environment variables."""

import os
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

from dotenv import dotenv_values

from pkostat.errors import PkoStatError

DEFAULT_OLLAMA_URL = "http://localhost:11434"
DEFAULT_OLLAMA_MODEL = "gpt-oss:20b"

ENV_TEMPLATE = f"""\
# PkoStat settings. Environment variables with the same names take precedence.
# Supabase project URL, e.g. https://<project>.supabase.co
SUPABASE_URL=
# Secret (service role) key: reads and deletes the inbox. Never put it on the phone.
SUPABASE_SECRET_KEY=
OLLAMA_URL={DEFAULT_OLLAMA_URL}
OLLAMA_MODEL={DEFAULT_OLLAMA_MODEL}
# Where backups go (default: <data folder>/backups). A cloud-synced folder keeps them off this PC.
PKOSTAT_BACKUP_DIR=
# Publishing encrypted read-only reports to GitHub Pages: the repository to push the gh-pages
# branch to (e.g. git@github.com:<owner>/<repo>.git). Empty = publishing is off.
PKOSTAT_PUBLISH_REMOTE=
# The site address; empty = derived from a GitHub remote (https://<owner>.github.io/<repo>).
PKOSTAT_PUBLISH_URL=
"""


@dataclass(frozen=True, slots=True)
class Settings:
    home: Path
    supabase_url: str | None
    supabase_secret_key: str | None
    ollama_url: str
    ollama_model: str
    backup_dir: Path | None = None  # PKOSTAT_BACKUP_DIR, e.g. a folder synced to a cloud drive
    publish_remote: str | None = None  # PKOSTAT_PUBLISH_REMOTE: git remote for the gh-pages branch
    publish_url: str | None = None  # PKOSTAT_PUBLISH_URL: the site address, if not derivable

    @property
    def env_path(self) -> Path:
        return self.home / ".env"

    @property
    def db_path(self) -> Path:
        return self.home / "db" / "pkostat.db"

    @property
    def reports_dir(self) -> Path:
        return self.home / "reports"

    @property
    def backups_dir(self) -> Path:
        return self.backup_dir or self.home / "backups"

    def require_supabase(self) -> tuple[str, str]:
        if not self.supabase_url or not self.supabase_secret_key:
            raise PkoStatError(
                f"SUPABASE_URL and SUPABASE_SECRET_KEY must be set in {self.env_path} "
                "or in the environment."
            )
        return self.supabase_url, self.supabase_secret_key


def load_settings(environ: Mapping[str, str] | None = None) -> Settings:
    env = os.environ if environ is None else environ
    home = Path(env.get("PKOSTAT_HOME") or Path.home() / "pkostatistics").expanduser()
    values = {**_read_env_file(home / ".env"), **env}
    return Settings(
        home=home,
        supabase_url=_non_empty(values.get("SUPABASE_URL")),
        supabase_secret_key=_non_empty(values.get("SUPABASE_SECRET_KEY")),
        ollama_url=_non_empty(values.get("OLLAMA_URL")) or DEFAULT_OLLAMA_URL,
        ollama_model=_non_empty(values.get("OLLAMA_MODEL")) or DEFAULT_OLLAMA_MODEL,
        backup_dir=_path(values.get("PKOSTAT_BACKUP_DIR")),
        publish_remote=_non_empty(values.get("PKOSTAT_PUBLISH_REMOTE")),
        publish_url=_non_empty(values.get("PKOSTAT_PUBLISH_URL")),
    )


def _read_env_file(path: Path) -> dict[str, str]:
    if not path.is_file():
        return {}
    return {key: value for key, value in dotenv_values(path).items() if value is not None}


def _path(value: str | None) -> Path | None:
    cleaned = _non_empty(value)
    return Path(cleaned).expanduser() if cleaned else None


def _non_empty(value: str | None) -> str | None:
    if value is None:
        return None
    stripped = value.strip()
    return stripped or None
