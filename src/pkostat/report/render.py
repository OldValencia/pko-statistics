"""Rendering ReportData into one HTML file: CSS, JS and data are inlined, nothing is fetched."""

import json
from importlib.resources import files
from typing import Literal

from jinja2 import Environment, PackageLoader, select_autoescape

from pkostat.analytics.model import ReportData

Mode = Literal["user", "admin"]

ADMIN_PAGES = [
    ("budgets", "Бюджеты"),
    ("categories", "Категории"),
    ("data", "Данные"),
    ("users", "Пользователи"),
]
# The uncategorised page has its own nav button with a counter, so it is not in ADMIN_PAGES.

_env = Environment(
    loader=PackageLoader("pkostat.report", "templates"),
    autoescape=select_autoescape(["html", "j2"]),
    keep_trailing_newline=True,
)


def render_report(
    data: ReportData,
    mode: Mode,
    admin: dict[str, object] | None = None,
) -> str:
    """The user mode is the read-only page that may be published: it carries no admin data and
    no admin code. The admin mode is served by the local app only."""
    payload: dict[str, object] = {
        "report": data.model_dump(mode="json"),
        "mode": mode,
    }
    if mode == "admin":
        payload["admin"] = admin or {}
    scripts = _scripts("js") + (_scripts("admin") if mode == "admin" else "")
    return _env.get_template("report.html.j2").render(
        user=data.user,
        mode=mode,
        admin_pages=ADMIN_PAGES,
        users=(admin or {}).get("users", []),
        current_user=(admin or {}).get("current_user"),
        css=_static("report.css"),
        js=scripts,
        data_json=_script_safe_json(payload),
    )


def _script_safe_json(payload: object) -> str:
    # Inside <script>, "</script>" or "<!--" in the data would end or break the element. "<" only
    # occurs inside JSON strings, where \u003c means the same character to JSON.parse.
    text = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    return text.replace("<", "\\u003c")


def _static(name: str) -> str:
    return files("pkostat.report").joinpath("static", name).read_text("utf-8")


def _scripts(kind: str) -> str:
    folder = files("pkostat.report").joinpath("static", kind)
    names = sorted(entry.name for entry in folder.iterdir() if entry.name.endswith(".js"))
    return "\n".join(folder.joinpath(name).read_text("utf-8") for name in names)
