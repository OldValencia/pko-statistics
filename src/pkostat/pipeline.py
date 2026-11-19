"""`pkostat run`: the whole cycle in one go, for a daily scheduled task or the "update all" button.

A step that fails (no internet, Ollama not started) is reported and the rest still runs: fresh
reports and a backup are worth having even when the LLM is off.
"""

import logging
import sqlite3
from collections.abc import Callable
from dataclasses import dataclass

from pkostat.backup import create_backup
from pkostat.categorize.config import load_category_config
from pkostat.config import Settings
from pkostat.db.users import list_users
from pkostat.errors import PkoStatError
from pkostat.home import open_database
from pkostat.ingest.supabase import SupabaseInbox
from pkostat.ingest.sync import sync_inbox
from pkostat.llm.merchants import suggest_categories
from pkostat.llm.ollama import OllamaClient
from pkostat.publish.service import publish_reports
from pkostat.rebuild import rebuild
from pkostat.report.render import render_report
from pkostat.report_service import report_data_for

log = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class Step:
    name: str
    ok: bool
    message: str


def run_all(settings: Settings, use_llm: bool = True) -> list[Step]:
    steps: list[Step] = []
    conn = open_database(settings)
    try:
        _step(steps, "Синхронизация", lambda: _sync(conn, settings))
        _step(steps, "Пересборка", lambda: _rebuild(conn, settings))
        if use_llm:
            _step(steps, "LLM: подсказки категорий", lambda: _suggest(conn, settings))
        _step(steps, "Отчёты", lambda: _reports(conn, settings))
        _step(steps, "Публикация", lambda: publish_message(conn, settings))
    finally:
        conn.close()
    _step(steps, "Резервная копия", lambda: f"{create_backup(settings).name}")
    return steps


def _step(steps: list[Step], name: str, action: Callable[[], str]) -> None:
    try:
        steps.append(Step(name, True, action()))
    except PkoStatError as exc:
        steps.append(Step(name, False, str(exc)))
    except Exception as exc:  # one broken step must not cost the backup at the end
        log.exception("Step %s failed", name)
        steps.append(Step(name, False, f"{type(exc).__name__}: {exc}"))


def _sync(conn: sqlite3.Connection, settings: Settings) -> str:
    if not (settings.supabase_url and settings.supabase_secret_key):
        return "пропущено: Supabase не настроен"
    url, key = settings.require_supabase()
    with SupabaseInbox(url, key) as inbox:
        result = sync_inbox(conn, inbox)
    return f"новых уведомлений {result.stored}, отклонено {result.rejected}"


def _rebuild(conn: sqlite3.Connection, settings: Settings) -> str:
    result = rebuild(conn, None, load_category_config(settings.home))
    return f"операций {result.counted}, без категории {result.uncategorised}"


def _suggest(conn: sqlite3.Connection, settings: Settings) -> str:
    config = load_category_config(settings.home)
    with OllamaClient(settings.ollama_url, settings.ollama_model) as model:
        result = suggest_categories(conn, model, config)
    if not result.asked:
        return "новых мерчантов нет"
    return f"подсказок {result.confident + result.unsure}, подтверди их на странице «Без категории»"


def publish_message(conn: sqlite3.Connection, settings: Settings) -> str:
    if not settings.publish_remote:
        return "пропущено: публикация не настроена"
    result = publish_reports(conn, settings)
    if not result.reports:
        return "ни у кого не открыт доступ по ссылке" + (", сайт очищен" if result.changed else "")
    return f"опубликовано отчётов: {result.reports}" if result.changed else "без изменений"


def _reports(conn: sqlite3.Connection, settings: Settings) -> str:
    users = list_users(conn)
    for user in users:
        data = report_data_for(conn, settings, user)
        out = settings.reports_dir / user.name / "report.html"
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(render_report(data, "user"), encoding="utf-8")
    return f"обновлено {len(users)}"
