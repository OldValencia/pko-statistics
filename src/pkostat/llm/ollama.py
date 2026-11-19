"""A minimal Ollama chat client with structured output."""

import logging
from importlib.resources import files
from typing import Protocol

import httpx
from pydantic import BaseModel, ValidationError

from pkostat.errors import PkoStatError

log = logging.getLogger(__name__)

# The default Ollama context is small and silently truncates long prompts.
CONTEXT_TOKENS = 16_384
ATTEMPTS = 2


class ChatModel(Protocol):
    model: str

    def chat[T: BaseModel](
        self, system: str, user: str, schema: type[T], think: str = "low"
    ) -> T: ...


class OllamaClient:
    def __init__(
        self,
        url: str,
        model: str,
        timeout: float = 600.0,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self.model = model
        self._url = url.rstrip("/") + "/api/chat"
        self._client = httpx.Client(
            timeout=httpx.Timeout(timeout, connect=5.0), transport=transport
        )

    def chat[T: BaseModel](self, system: str, user: str, schema: type[T], think: str = "low") -> T:
        """`think` is gpt-oss's reasoning effort: low for lookups, medium for writing."""
        body = {
            "model": self.model,
            "stream": False,
            "format": schema.model_json_schema(),
            "think": think,
            "options": {"temperature": 0, "num_ctx": CONTEXT_TOKENS},
            "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
        }
        last_error: Exception | None = None
        for attempt in range(1, ATTEMPTS + 1):
            content = self._post(body)
            try:
                return schema.model_validate_json(content)
            except ValidationError as exc:
                last_error = exc
                log.warning("Ollama answer did not match the schema (attempt %d): %s", attempt, exc)
        raise PkoStatError(f"The model's answer did not match the expected format: {last_error}")

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> OllamaClient:
        return self

    def __exit__(self, *exc_info: object) -> None:
        self.close()

    def _post(self, body: dict[str, object]) -> str:
        try:
            response = self._client.post(self._url, json=body)
        except httpx.ConnectError as exc:
            raise PkoStatError(f"Ollama is not running at {self._url}: start Ollama.") from exc
        except httpx.TimeoutException as exc:
            raise PkoStatError("Ollama did not answer in time.") from exc
        if response.status_code == 404:
            raise PkoStatError(
                f"Model {self.model!r} is not installed: `ollama pull {self.model}`."
            )
        if response.is_error:
            raise PkoStatError(f"Ollama error {response.status_code}: {response.text[:300]}")
        return response.json()["message"]["content"]


def prompt(name: str) -> str:
    return files("pkostat.llm").joinpath("prompts", name).read_text("utf-8")
