"""The local LLM from the app: category suggestions the owner then confirms."""

from fastapi import FastAPI
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from pkostat.clock import now_local_iso
from pkostat.db.categories import set_rule
from pkostat.errors import PkoStatError
from pkostat.llm.merchants import suggest_categories
from pkostat.llm.ollama import OllamaClient
from pkostat.web.context import Context


class Choice(BaseModel):
    merchant: str
    category: str


class Choices(BaseModel):
    items: list[Choice]


def register(app: FastAPI, ctx: Context) -> None:
    @app.post("/api/llm/suggest")
    def suggest() -> JSONResponse:
        with (
            ctx.db() as conn,
            OllamaClient(ctx.settings.ollama_url, ctx.settings.ollama_model) as model,
        ):
            result = suggest_categories(conn, model, ctx.config())
        if not result.asked:
            return JSONResponse({"ok": True, "message": "Новых мерчантов нет."})
        return JSONResponse(
            {
                "ok": True,
                "message": f"LLM предложила категории для {result.asked} мерчантов "
                f"(уверенно: {result.confident}). Проверь и прими.",
            }
        )

    @app.post("/api/merchants/accept")
    def accept(body: Choices) -> JSONResponse:
        """The owner's confirmed choices, often the LLM's suggestions: stored as manual rules."""
        config = ctx.config()
        unknown = sorted({c.category for c in body.items if c.category not in config.categories})
        if unknown:
            raise PkoStatError(f"Unknown categories: {', '.join(unknown)}.")
        with ctx.db() as conn:
            with conn:
                for choice in body.items:
                    set_rule(conn, choice.merchant, choice.category, "manual", now_local_iso())
            return ctx.done(conn, f"Сохранено правил: {len(body.items)}.")
