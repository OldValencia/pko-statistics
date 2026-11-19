"""The Supabase inbox: the phone inserts notifications, this client reads and deletes them."""

from collections.abc import Sequence
from typing import Protocol

import httpx
from pydantic import AwareDatetime, BaseModel, ConfigDict, ValidationError

from pkostat.errors import PkoStatError

TABLE_PATH = "/rest/v1/notifications"
# Keeps DELETE URLs short: ids go into the query string.
DELETE_CHUNK = 100


class InboxRow(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: int
    created_at: AwareDatetime
    token_id: str
    notification_text: str


class Inbox(Protocol):
    def fetch_after(self, after_id: int, limit: int) -> list[InboxRow]: ...

    def delete(self, ids: Sequence[int]) -> None: ...


class SupabaseInbox:
    def __init__(
        self, project_url: str, secret_key: str, transport: httpx.BaseTransport | None = None
    ) -> None:
        if "/rest/" in project_url:
            raise PkoStatError(
                "SUPABASE_URL must be the project URL, e.g. https://<project>.supabase.co"
            )
        self._url = project_url.rstrip("/") + TABLE_PATH
        self._client = httpx.Client(
            headers={"apikey": secret_key},
            timeout=httpx.Timeout(15.0),
            transport=transport,
        )

    def fetch_after(self, after_id: int, limit: int) -> list[InboxRow]:
        response = self._request(
            "GET",
            params={
                "select": "id,created_at,token_id,notification_text",
                "id": f"gt.{after_id}",
                "order": "id.asc",
                "limit": str(limit),
            },
        )
        try:
            return [InboxRow.model_validate(row) for row in response.json()]
        except (ValueError, ValidationError) as exc:
            raise PkoStatError(f"Unexpected response from Supabase: {exc}") from exc

    def delete(self, ids: Sequence[int]) -> None:
        for start in range(0, len(ids), DELETE_CHUNK):
            chunk = ids[start : start + DELETE_CHUNK]
            self._request(
                "DELETE",
                params={"id": f"in.({','.join(str(i) for i in chunk)})"},
                headers={"Prefer": "return=minimal"},
            )

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> SupabaseInbox:
        return self

    def __exit__(self, *exc_info: object) -> None:
        self.close()

    def _request(
        self, method: str, params: dict[str, str], headers: dict[str, str] | None = None
    ) -> httpx.Response:
        try:
            response = self._client.request(method, self._url, params=params, headers=headers)
        except httpx.RequestError as exc:
            raise PkoStatError(f"Cannot reach Supabase: {exc}") from exc
        if response.is_error:
            raise PkoStatError(
                f"Supabase {method} failed with HTTP {response.status_code}: {response.text[:300]}"
            )
        return response
