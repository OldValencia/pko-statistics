import json

import httpx
import pytest

from pkostat.errors import PkoStatError
from pkostat.ingest.supabase import DELETE_CHUNK, SupabaseInbox

PROJECT = "https://example.supabase.co"
ROW = {
    "id": 7,
    "created_at": "2026-11-16T10:26:43.123+00:00",
    "token_id": "00000000-1111-4222-8333-444444444444",
    "notification_text": "Payment card authorization\nAmount: 141,65 PLN.",
}


def _inbox(handler: httpx.MockTransport) -> SupabaseInbox:
    return SupabaseInbox(PROJECT, "sb_secret_test", transport=handler)


def test_fetch_after_builds_query_and_parses_rows() -> None:
    seen: list[httpx.Request] = []

    def handle(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(200, json=[ROW])

    with _inbox(httpx.MockTransport(handle)) as inbox:
        rows = inbox.fetch_after(5, 500)

    assert rows[0].id == 7
    assert rows[0].created_at.utcoffset() is not None
    request = seen[0]
    assert request.url.path == "/rest/v1/notifications"
    assert request.url.params["id"] == "gt.5"
    assert request.url.params["order"] == "id.asc"
    assert request.url.params["limit"] == "500"
    assert request.headers["apikey"] == "sb_secret_test"


def test_delete_is_chunked() -> None:
    seen: list[str] = []

    def handle(request: httpx.Request) -> httpx.Response:
        assert request.method == "DELETE"
        seen.append(request.url.params["id"])
        return httpx.Response(204)

    with _inbox(httpx.MockTransport(handle)) as inbox:
        inbox.delete(list(range(1, DELETE_CHUNK + 3)))

    assert len(seen) == 2
    assert seen[1] == f"in.({DELETE_CHUNK + 1},{DELETE_CHUNK + 2})"


def test_delete_nothing_sends_nothing() -> None:
    def handle(request: httpx.Request) -> httpx.Response:
        raise AssertionError("no request expected")

    with _inbox(httpx.MockTransport(handle)) as inbox:
        inbox.delete([])


def test_http_error_becomes_user_error() -> None:
    def handle(request: httpx.Request) -> httpx.Response:
        return httpx.Response(401, text=json.dumps({"message": "Invalid API key"}))

    with (
        _inbox(httpx.MockTransport(handle)) as inbox,
        pytest.raises(PkoStatError, match=r"HTTP 401.*Invalid API key"),
    ):
        inbox.fetch_after(0, 10)


def test_network_error_becomes_user_error() -> None:
    def handle(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("offline", request=request)

    with _inbox(httpx.MockTransport(handle)) as inbox, pytest.raises(PkoStatError, match="reach"):
        inbox.fetch_after(0, 10)


def test_unexpected_payload_becomes_user_error() -> None:
    def handle(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=[{"id": "not-a-number"}])

    with (
        _inbox(httpx.MockTransport(handle)) as inbox,
        pytest.raises(PkoStatError, match="Unexpected"),
    ):
        inbox.fetch_after(0, 10)


def test_rest_url_is_refused() -> None:
    with pytest.raises(PkoStatError, match="project URL"):
        SupabaseInbox(f"{PROJECT}/rest/v1/notifications", "key")
