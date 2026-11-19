import json
import sqlite3

import httpx
import pytest
from pydantic import BaseModel

from pkostat.categorize.config import load_category_config
from pkostat.db.categories import stored_rules
from pkostat.db.notifications import insert_raw_notification
from pkostat.db.suggestions import list_suggestions
from pkostat.errors import PkoStatError
from pkostat.llm.merchants import suggest_categories, unknown_merchants
from pkostat.llm.ollama import OllamaClient
from pkostat.rebuild import rebuild
from pkostat.users import add_user


class Answer(BaseModel):
    word: str


class FakeModel:
    """Returns prepared answers; records what it was asked."""

    model = "fake-model"

    def __init__(self, *answers: dict) -> None:
        self.answers = list(answers)
        self.questions: list[tuple[str, str]] = []

    def chat(self, system, user, schema, think="low"):
        self.questions.append((system, user))
        self.thinking = think
        return schema.model_validate(self.answers.pop(0))


def ollama(handler) -> OllamaClient:
    return OllamaClient(
        "http://ollama:11434", "gpt-oss:20b", transport=httpx.MockTransport(handler)
    )


def reply(content: str) -> httpx.Response:
    return httpx.Response(200, json={"message": {"content": content}})


def test_ollama_sends_schema_and_parses() -> None:
    seen = []

    def handle(request: httpx.Request) -> httpx.Response:
        seen.append(json.loads(request.content))
        return reply('{"word": "ok"}')

    assert ollama(handle).chat("sys", "user", Answer).word == "ok"
    body = seen[0]
    assert body["format"]["properties"]["word"]["type"] == "string"
    assert body["options"]["num_ctx"] >= 16384 and body["options"]["temperature"] == 0
    assert [m["role"] for m in body["messages"]] == ["system", "user"]


def test_ollama_retries_once_then_gives_up() -> None:
    answers = iter(["not json", '{"word": "second"}', "bad", "bad"])

    assert ollama(lambda r: reply(next(answers))).chat("s", "u", Answer).word == "second"
    with pytest.raises(PkoStatError, match="expected format"):
        ollama(lambda r: reply(next(answers))).chat("s", "u", Answer)


def test_ollama_errors_are_readable() -> None:
    def offline(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("refused", request=request)

    with pytest.raises(PkoStatError, match="not running"):
        ollama(offline).chat("s", "u", Answer)
    with pytest.raises(PkoStatError, match="ollama pull"):
        ollama(lambda r: httpx.Response(404, text="model not found")).chat("s", "u", Answer)


def _push(db: sqlite3.Connection, user_id: int, remote_id: int, place: str, amount: str) -> None:
    text = (
        f"Payment card authorization\nAmount: {amount} PLN.\nPlace: {place}, Gdansk.\n"
        f"Date: 2026-11-0{remote_id} 12:00:00."
    )
    with db:
        insert_raw_notification(db, user_id, remote_id, "2026-11-01T12:00:00", text)


def test_suggestions_are_stored_not_applied(db: sqlite3.Connection) -> None:
    user = add_user(db, "alice")
    _push(db, user.id, 1, "GASTRONOMIA KOWAL", "12,00")
    _push(db, user.id, 2, "SKLEP PHU NOWAK 757", "200,00")
    _push(db, user.id, 3, "WOLT", "50,00")  # known by rules: an example, not a question
    config = load_category_config()
    rebuild(db, None, config)
    model = FakeModel({"items": [
        {"merchant": "GASTRONOMIA KOWAL", "category": "Restaurants & cafes", "confidence": 0.9},
        {"merchant": "SKLEP PHU NOWAK", "category": "Other", "confidence": 0.9},
        {"merchant": "INVENTED", "category": "Groceries", "confidence": 1.0},
    ]})  # fmt: skip

    result = suggest_categories(db, model, config)

    assert (result.asked, result.confident, result.unsure) == (2, 1, 1)
    assert {k: (s.category, s.confidence) for k, s in list_suggestions(db).items()} == {
        "GASTRONOMIA KOWAL": ("Restaurants & cafes", 0.9),
        "SKLEP PHU NOWAK": ("Other", 0.9),
    }
    assert stored_rules(db) == {}  # nothing applied without the owner
    rebuild(db, None, config)
    assert len(unknown_merchants(db)) == 2
    system, question = model.questions[0]
    assert "WOLT -> Food delivery" in system  # the owner's taxonomy as examples
    assert model.thinking == "medium"
    assert json.loads(question)[0]["merchant"] == "SKLEP PHU NOWAK"  # biggest first
