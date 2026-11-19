import json
import re
import sqlite3
from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from httpx import Response
from statement_data import CARD, PENDING, PHONE_OUT, write_statement

from pkostat.categorize.config import load_category_config
from pkostat.cli import main
from pkostat.config import load_settings
from pkostat.web.app import create_app

OURS = {"Origin": "http://testserver", "X-PkoStat": "1"}
LIDL_ROW = ["2026-11-14", "2026-11-14", "Płatność kartą", "-9.99", "PLN", "+1.00",
            "Lokalizacja: Adres: LIDL X Miasto: B Kraj: POLSKA"]  # fmt: skip


@pytest.fixture
def client(home: Path) -> Iterator[TestClient]:
    main(["init"])
    main(["user", "add", "alice", "--display-name", "Alice"])
    statement = write_statement(home / "s 01.11.2026 - 12.11.2026.csv", [CARD, PHONE_OUT, PENDING])
    main(["import-csv", str(statement), "--user", "alice"])
    with TestClient(create_app(load_settings(), {"testserver"})) as test_client:
        yield test_client


def post(client: TestClient, path: str, body: object = None, **headers: str) -> Response:
    return client.post(path, json=body, headers={**OURS, **headers})


def query(home: Path, sql: str) -> list[sqlite3.Row]:
    with sqlite3.connect(home / "db" / "pkostat.db") as conn:
        conn.row_factory = sqlite3.Row
        return conn.execute(sql).fetchall()


def payload(response: Response) -> dict:
    found = re.search(
        r'<script type="application/json" id="data">(.*?)</script>', response.text, re.S
    )
    assert found is not None
    return json.loads(found.group(1))


def test_admin_page(client: TestClient) -> None:
    response = client.get("/")

    assert response.status_code == 200
    assert payload(response)["mode"] == "admin"
    assert payload(response)["admin"]["current_user"] == "alice"
    assert 'id="userSwitch"' in response.text
    assert response.headers["x-frame-options"] == "DENY"


def test_foreign_host_and_cross_site_posts_are_refused(client: TestClient) -> None:
    assert client.get("/", headers={"Host": "evil.example"}).status_code == 403
    assert client.post("/api/rebuild").status_code == 403
    assert post(client, "/api/rebuild", Origin="http://evil.example").status_code == 403
    no_header = client.post("/api/rebuild", headers={"Origin": "http://testserver"})
    assert no_header.status_code == 403
    assert post(client, "/api/rebuild").status_code == 200


def test_merchant_rule(client: TestClient, home: Path) -> None:
    body = {"merchant": "JANE DOE", "category": "Rent & utilities"}

    assert post(client, "/api/merchants/category", body).status_code == 200

    rows = query(home, "SELECT category FROM transactions WHERE merchant_key = 'JANE DOE'")
    assert [row["category"] for row in rows] == ["Rent & utilities"]


def test_single_transaction_override(client: TestClient, home: Path) -> None:
    sql = "SELECT source, source_id, status, category FROM transactions WHERE merchant_key = 'WOLT'"
    booked = next(row for row in query(home, sql) if row["status"] == "settled")
    tx_id = booked["source"][0] + str(booked["source_id"])

    assert (
        post(client, f"/api/transactions/{tx_id}/category", {"category": "Groceries"}).status_code
        == 200
    )

    assert [row["category"] for row in query(home, sql)] == ["Groceries"]
    others = query(home, "SELECT category FROM transactions WHERE merchant_key = 'BOLT'")
    assert [row["category"] for row in others] == ["Taxi & scooters"]  # untouched


def test_unknown_category_is_rejected(client: TestClient) -> None:
    response = post(client, "/api/merchants/category", {"merchant": "WOLT", "category": "Nope"})

    assert response.status_code == 400
    assert "Unknown category" in response.json()["error"]


def test_csv_upload(client: TestClient, home: Path) -> None:
    data = write_statement(home / "n.csv", [CARD, LIDL_ROW]).read_bytes()

    response = client.post(
        "/api/import?user=alice",
        content=data,
        headers={
            **OURS,
            "X-File-Name": "n%2014.11.csv",
            "Content-Type": "application/octet-stream",
        },
    )

    assert response.status_code == 200, response.text
    assert "новых строк 1" in response.json()["message"]
    rows = query(home, "SELECT category FROM transactions WHERE merchant_key = 'LIDL'")
    assert [row["category"] for row in rows] == ["Groceries"]


def test_users(client: TestClient) -> None:
    assert post(client, "/api/users", {"name": "bob", "display_name": "Bob B"}).status_code == 200
    assert post(client, "/api/users", {"name": "bob"}).status_code == 400
    assert (
        post(client, "/api/users/bob/display-name", {"display_name": "Robert"}).status_code == 200
    )
    before = {u["name"]: u["token"] for u in payload(client.get("/"))["admin"]["users"]}

    assert post(client, "/api/users/bob/rotate").status_code == 200

    after = {u["name"]: u for u in payload(client.get("/?user=bob"))["admin"]["users"]}
    assert after["bob"]["token"] != before["bob"]
    assert after["bob"]["label"] == "Robert"


def test_categories_edit_add_delete(client: TestClient, home: Path) -> None:
    edit = {"name": "Food delivery", "label": "Доставка", "kind": "impulse", "description": "Wolt"}
    assert post(client, "/api/categories", edit).status_code == 200
    assert (
        post(client, "/api/categories", {"label": "Котик", "kind": "discretionary"}).status_code
        == 200
    )

    config = load_category_config(home)
    assert config.categories["Food delivery"].display == "Доставка"
    assert config.categories["Котик"].kind == "discretionary"
    # Used by rules and transactions: refused. New and unused: removed.
    assert post(client, "/api/categories/delete", {"name": "Food delivery"}).status_code == 400
    assert post(client, "/api/categories/delete", {"name": "Котик"}).status_code == 200
    assert "Котик" not in load_category_config(home).categories


def test_sync_without_supabase(client: TestClient) -> None:
    response = post(client, "/api/sync")

    assert response.status_code == 400
    assert "SUPABASE" in response.json()["error"]


def test_budgets(client: TestClient) -> None:
    plan = {"user": "alice", "goal": 2000, "limits": {"Food delivery": 800, "Taxi & scooters": 0}}

    assert post(client, "/api/budgets", plan).status_code == 200
    admin = payload(client.get("/"))["admin"]
    assert admin["budget"] == {"goal": 200_000, "limits": {"Food delivery": 80_000}}
    bad = post(client, "/api/budgets", {"user": "alice", "limits": {"Nope": 10}})
    assert bad.status_code == 400
    assert post(client, "/api/budgets", {"user": "alice"}).json()["message"] == "План очищен."


def test_default_user_is_the_first_created(client: TestClient) -> None:
    post(client, "/api/users", {"name": "aaron"})  # sorts before alice

    assert payload(client.get("/"))["admin"]["current_user"] == "alice"


def test_accepting_suggestions_makes_manual_rules(client: TestClient, home: Path) -> None:
    body = {"items": [{"merchant": "JANE DOE", "category": "Rent & utilities"}]}

    assert post(client, "/api/merchants/accept", body).status_code == 200
    assert (
        post(
            client, "/api/merchants/accept", {"items": [{"merchant": "X", "category": "Nope"}]}
        ).status_code
        == 400
    )

    rows = query(home, "SELECT source FROM merchant_rules WHERE merchant_key = 'JANE DOE'")
    assert [row["source"] for row in rows] == ["manual"]
    assert "suggestions" in payload(client.get("/"))["admin"]


def test_alternatives_for_the_switch(client: TestClient) -> None:
    alternatives = payload(client.get("/"))["admin"]["alternatives"]

    assert alternatives["WOLT"] == {"main": "Food delivery", "alt": "Groceries"}
