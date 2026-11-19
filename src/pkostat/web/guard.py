"""Keeping other websites out of the local app.

Listening on 127.0.0.1 is not enough: any page open in the same browser can send requests to
localhost. Two checks close that:
- Host must be our own address — defeats DNS rebinding (evil.example resolving to 127.0.0.1);
- every change must be a POST carrying our Origin and the X-PkoStat header — a cross-site form or
  fetch either sends a foreign Origin or cannot add a custom header without a CORS preflight,
  which this app never approves.
"""

from collections.abc import Awaitable, Callable

from fastapi import Request, Response
from fastapi.responses import JSONResponse

SAFE_METHODS = frozenset({"GET", "HEAD"})
HEADER = "x-pkostat"

Handler = Callable[[Request], Awaitable[Response]]


def local_hosts(port: int) -> set[str]:
    return {f"127.0.0.1:{port}", f"localhost:{port}"}


def make_guard(hosts: set[str]) -> Callable[[Request, Handler], Awaitable[Response]]:
    origins = {f"http://{host}" for host in hosts}

    async def guard(request: Request, call_next: Handler) -> Response:
        if request.headers.get("host", "") not in hosts:
            return JSONResponse({"error": "Forbidden host."}, status_code=403)
        if request.method not in SAFE_METHODS and (
            request.headers.get("origin") not in origins or request.headers.get(HEADER) != "1"
        ):
            return JSONResponse({"error": "Cross-site request refused."}, status_code=403)
        response = await call_next(request)
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Cache-Control"] = "no-store"
        return response

    return guard
