"""Administration: users, their published reports, budgets and category definitions."""

import sqlite3

from fastapi import FastAPI
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from pkostat.categorize import editing
from pkostat.db.budgets import save_budget
from pkostat.domain import Budget
from pkostat.errors import PkoStatError
from pkostat.pipeline import publish_message
from pkostat.publish.sharing import close_share, open_share
from pkostat.users import add_user, get_user, rotate_token, set_display_name
from pkostat.web.context import Context, category_blockers


class NewUser(BaseModel):
    name: str
    display_name: str | None = None
    token: str | None = None


class DisplayName(BaseModel):
    display_name: str | None


class BudgetForm(BaseModel):
    user: str
    goal: float | None = None  # złoty a month
    limits: dict[str, float] = {}  # category name -> złoty a month


class CategoryForm(BaseModel):
    name: str | None = None  # None: a new category
    label: str = ""
    kind: str = "other"
    description: str = ""
    month_shift_from_day: int | None = None


def register(app: FastAPI, ctx: Context) -> None:
    @app.post("/api/users")
    def create_user(body: NewUser) -> JSONResponse:
        with ctx.db() as conn:
            created = add_user(conn, body.name, body.token or None, body.display_name)
            return ctx.done(conn, f"Пользователь {created.name} добавлен.")

    @app.post("/api/users/{name}/display-name")
    def display_name(name: str, body: DisplayName) -> JSONResponse:
        with ctx.db() as conn:
            set_display_name(conn, name, body.display_name)
            return ctx.done(conn, "Имя сохранено.")

    @app.post("/api/users/{name}/rotate")
    def rotate(name: str) -> JSONResponse:
        with ctx.db() as conn:
            rotate_token(conn, name)
            return ctx.done(conn, "Новый токен выпущен — обнови его в Shortcut.")

    @app.post("/api/users/{name}/share")
    def share(name: str) -> JSONResponse:
        with ctx.db() as conn:
            open_share(conn, name)
            return ctx.done(conn, "Новая ссылка. " + _publish(ctx, conn))

    @app.post("/api/users/{name}/share/delete")
    def unshare(name: str) -> JSONResponse:
        with ctx.db() as conn:
            close_share(conn, name)
            return ctx.done(conn, "Доступ по ссылке закрыт. " + _publish(ctx, conn))

    @app.post("/api/publish")
    def publish_now() -> JSONResponse:
        with ctx.db() as conn:
            return ctx.done(conn, "Публикация: " + _publish(ctx, conn))

    @app.post("/api/budgets")
    def save_plan(body: BudgetForm) -> JSONResponse:
        config = ctx.config()
        unknown = [name for name in body.limits if name not in config.categories]
        if unknown:
            raise PkoStatError(f"Unknown categories: {', '.join(unknown)}.")
        plan = Budget(
            goal=_grosze(body.goal),
            limits={name: g for name, zl in body.limits.items() if (g := _grosze(zl))},
        )
        with ctx.db() as conn:
            user = get_user(conn, body.user)
            with conn:
                save_budget(conn, user.id, plan)
            return ctx.done(conn, "План сохранён." if not plan.empty else "План очищен.")

    @app.post("/api/categories")
    def save_category(body: CategoryForm) -> JSONResponse:
        config = ctx.config()
        if body.name is None:
            categories = editing.add_category(config, body.label, body.kind, body.description)
        else:
            categories = editing.update_category(
                config,
                body.name,
                body.label,
                body.kind,
                body.description,
                body.month_shift_from_day,
            )
        editing.save_categories(ctx.settings.home, categories)
        with ctx.db() as conn:
            return ctx.done(conn, "Категория сохранена.")

    @app.post("/api/categories/delete")
    def delete_category(body: CategoryForm) -> JSONResponse:
        config, name = ctx.config(), body.name or ""
        with ctx.db() as conn:
            categories = editing.remove_category(
                config, name, category_blockers(conn, config, name)
            )
            editing.save_categories(ctx.settings.home, categories)
            return ctx.done(conn, "Категория удалена.")


def _publish(ctx: Context, conn: sqlite3.Connection) -> str:
    try:
        return publish_message(conn, ctx.settings) + "."
    except PkoStatError as exc:
        return f"Не опубликовано: {exc}"


def _grosze(zl: float | None) -> int | None:
    """Positive złoty to grosze; empty, zero or negative means "not set"."""
    if zl is None or zl <= 0:
        return None
    if zl > 1_000_000:
        raise PkoStatError("That is more than a million złoty a month.")
    return round(zl * 100)
