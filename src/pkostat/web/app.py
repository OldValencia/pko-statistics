"""The local admin app: pages are GET, every change is a POST to /api/…, then a page reload."""

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse

from pkostat.config import Settings
from pkostat.db.users import list_users
from pkostat.errors import PkoStatError
from pkostat.users import get_user
from pkostat.web import routes_admin, routes_data, routes_llm
from pkostat.web.context import Context
from pkostat.web.guard import make_guard
from pkostat.web.pages import admin_page


def create_app(settings: Settings, hosts: set[str]) -> FastAPI:
    app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)
    app.middleware("http")(make_guard(hosts))
    ctx = Context(settings)

    @app.exception_handler(PkoStatError)
    async def user_error(request: Request, exc: PkoStatError) -> JSONResponse:
        return JSONResponse({"error": str(exc)}, status_code=400)

    @app.get("/", response_class=HTMLResponse)
    def index(user: str | None = None) -> str:
        with ctx.db() as conn:
            # Without ?user=, the first user created: the owner of the PC, not the first by name.
            users = list_users(conn)
            chosen = get_user(conn, user) if user else min(users, key=lambda u: u.id, default=None)
            return admin_page(conn, settings, ctx.config(), chosen)

    routes_data.register(app, ctx)
    routes_admin.register(app, ctx)
    routes_llm.register(app, ctx)
    return app
