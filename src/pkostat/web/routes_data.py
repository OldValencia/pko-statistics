"""Changing data: categories of operations and merchants, statement upload, sync, rebuild."""

from urllib.parse import unquote

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from pkostat.backup import create_backup
from pkostat.categorize.config import CategoryConfig
from pkostat.clock import now_local_iso
from pkostat.db.categories import delete_override, delete_rule, set_override, set_rule
from pkostat.errors import PkoStatError
from pkostat.ingest.supabase import SupabaseInbox
from pkostat.ingest.sync import sync_inbox
from pkostat.pipeline import run_all
from pkostat.statement_import import import_uploaded
from pkostat.users import get_user
from pkostat.web.context import Context

MAX_UPLOAD = 20 * 1024 * 1024
SOURCES = {"c": "csv", "n": "notification"}


class CategoryChoice(BaseModel):
    category: str | None


class MerchantChoice(BaseModel):
    merchant: str
    category: str | None = None


def register(app: FastAPI, ctx: Context) -> None:
    @app.post("/api/transactions/{tx_id}/category")
    def transaction_category(tx_id: str, body: CategoryChoice) -> JSONResponse:
        source, number = SOURCES.get(tx_id[:1]), tx_id[1:]
        if source is None or not number.isdigit():
            raise PkoStatError(f"Unknown transaction {tx_id!r}.")
        _check_category(ctx.config(), body.category)
        with ctx.db() as conn:
            with conn:
                if body.category is None:
                    delete_override(conn, source, int(number))
                else:
                    set_override(conn, source, int(number), body.category)
            return ctx.done(conn, "Категория операции сохранена.")

    @app.post("/api/merchants/category")
    def merchant_category(body: MerchantChoice) -> JSONResponse:
        _check_category(ctx.config(), body.category)
        with ctx.db() as conn:
            with conn:
                if body.category is None:
                    delete_rule(conn, body.merchant)
                else:
                    set_rule(conn, body.merchant, body.category, "manual", now_local_iso())
            return ctx.done(conn, f"Правило для {body.merchant} сохранено.")

    @app.post("/api/rules/delete")
    def remove_rule(body: MerchantChoice) -> JSONResponse:
        with ctx.db() as conn:
            with conn:
                delete_rule(conn, body.merchant)
            return ctx.done(conn, f"Правило для {body.merchant} удалено.")

    @app.post("/api/import")
    async def import_csv(request: Request, user: str) -> JSONResponse:
        data = await request.body()
        if not data or len(data) > MAX_UPLOAD:
            raise PkoStatError("Файл пустой или больше 20 МБ.")
        name = unquote(request.headers.get("x-file-name", "statement.csv"))
        with ctx.db() as conn:
            result = import_uploaded(conn, get_user(conn, user), name, data)
            return ctx.done(
                conn,
                f"{result.file_name}: новых строк {result.new_rows}, уже были {result.known_rows}.",
            )

    @app.post("/api/sync")
    def sync() -> JSONResponse:
        url, key = ctx.settings.require_supabase()
        with ctx.db() as conn, SupabaseInbox(url, key) as inbox:
            result = sync_inbox(conn, inbox)
            return ctx.done(
                conn, f"Новых уведомлений: {result.stored}, отклонено: {result.rejected}."
            )

    @app.post("/api/backup")
    def backup_now() -> JSONResponse:
        return JSONResponse({"ok": True, "message": f"Копия: {create_backup(ctx.settings).name}"})

    @app.post("/api/run")
    def run_everything() -> JSONResponse:
        steps = run_all(ctx.settings)
        failed = [f"{s.name}: {s.message}" for s in steps if not s.ok]
        done = ", ".join(f"{s.name.lower()} — {s.message}" for s in steps if s.ok)
        message = "Готово: " + done + (". Не вышло: " + "; ".join(failed) if failed else ".")
        return JSONResponse({"ok": True, "message": message})

    @app.post("/api/rebuild")
    def rebuild_all() -> JSONResponse:
        with ctx.db() as conn:
            return ctx.done(conn, "Данные пересобраны.")


def _check_category(config: CategoryConfig, name: str | None) -> None:
    if name is not None and name not in config.categories:
        raise PkoStatError(f"Unknown category {name!r}.")
