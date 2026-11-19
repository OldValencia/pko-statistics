"""The files of the published site: one locked page per shared user and nothing else readable."""

import json
from dataclasses import dataclass
from importlib.resources import files

from pkostat.publish.crypto import seal

PLACEHOLDER = "__PAYLOAD__"
INDEX = """<!doctype html><html lang="ru"><head><meta charset="utf-8">
<meta name="robots" content="noindex, nofollow"><title>PkoStat</title></head>
<body><p>Здесь ничего нет.</p></body></html>
"""
ROBOTS = "User-agent: *\nDisallow: /\n"


@dataclass(frozen=True, slots=True)
class Page:
    share_id: str
    password: str
    html: str


def locked_template() -> str:
    return files("pkostat.publish").joinpath("locked.html").read_text("utf-8")


def build_site(pages: list[Page]) -> dict[str, bytes]:
    template = locked_template()
    site = {
        "index.html": INDEX.encode("utf-8"),
        "robots.txt": ROBOTS.encode("utf-8"),
        ".nojekyll": b"",  # serve files as they are, no Jekyll processing
    }
    for page in pages:
        sealed = seal(page.html.encode("utf-8"), page.password)
        # Base64 and numbers only: nothing in it can end the <script> element.
        payload = json.dumps(sealed, separators=(",", ":"))
        site[f"{page.share_id}/index.html"] = template.replace(PLACEHOLDER, payload).encode("utf-8")
    return site
