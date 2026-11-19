import json
import re
import subprocess
from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from statement_data import CARD, PHONE_OUT, write_statement

from pkostat.cli import main
from pkostat.config import Settings, load_settings
from pkostat.db.users import User
from pkostat.errors import PkoStatError
from pkostat.publish.crypto import seal, unseal
from pkostat.publish.sharing import share_link, site_url
from pkostat.web.app import create_app

OURS = {"Origin": "http://testserver", "X-PkoStat": "1"}


def test_seal_round_trip() -> None:
    sealed = seal("<p>Привет</p>".encode(), "secret", iterations=1000)

    assert unseal(sealed, "secret") == "<p>Привет</p>".encode()
    assert sealed["salt"] != seal(b"x", "secret", iterations=1000)["salt"]
    with pytest.raises(PkoStatError, match="Wrong password"):
        unseal(sealed, "wrong")


@pytest.mark.parametrize(
    ("remote", "url"),
    [
        ("git@github.com:Jane/pko-stats.git", "https://jane.github.io/pko-stats"),
        ("https://github.com/Jane/pko-stats", "https://jane.github.io/pko-stats"),
        ("git@github.com:Jane/jane.github.io.git", "https://jane.github.io"),
        ("git@gitlab.com:Jane/pko-stats.git", None),
        (None, None),
    ],
)
def test_site_url(tmp_path: Path, remote: str | None, url: str | None) -> None:
    settings = Settings(tmp_path, None, None, "", "", publish_remote=remote)

    assert site_url(settings) == url


def test_share_link_carries_password_in_fragment(tmp_path: Path) -> None:
    settings = Settings(tmp_path, None, None, "", "", publish_url="https://example.org/r/")
    user = User(1, "jane", "t" * 20, "2026-11-19", None, "abc", "pw")

    assert share_link(settings, user) == "https://example.org/r/abc/#k=pw"
    assert share_link(settings, User(1, "jane", "t" * 20, "2026-11-19")) is None


@pytest.fixture
def remote(home: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    bare = home.parent / "site.git"
    subprocess.run(["git", "init", "-q", "--bare", str(bare)], check=True)
    monkeypatch.setenv("PKOSTAT_PUBLISH_REMOTE", str(bare))
    monkeypatch.setenv("PKOSTAT_PUBLISH_URL", "https://example.org/site")
    main(["init"])
    main(["user", "add", "alice", "--display-name", "Alice"])
    main(["user", "add", "bob"])
    statement = write_statement(home / "s 01.11.2026 - 12.11.2026.csv", [CARD, PHONE_OUT])
    main(["import-csv", str(statement), "--user", "alice"])
    return bare


def _published(bare: Path) -> dict[str, str]:
    def git(*args: str) -> str:
        return subprocess.run(
            ["git", "--git-dir", str(bare), *args],
            capture_output=True,
            text=True,
            encoding="utf-8",
            check=True,
        ).stdout

    names = git("ls-tree", "-r", "--name-only", "gh-pages").split()
    assert git("rev-list", "--count", "gh-pages").strip() == "1"  # history never piles up
    return {name: git("show", f"gh-pages:{name}") for name in names}


def _link(capsys: pytest.CaptureFixture[str], name: str) -> tuple[str, str]:
    main(["user", "share", name])
    found = re.search(r"https://example\.org/site/([\w-]+)/#k=([\w-]+)", capsys.readouterr().out)
    assert found is not None
    return found.group(1), found.group(2)


def test_publish_locks_each_shared_report(remote: Path, capsys: pytest.CaptureFixture[str]) -> None:
    share_id, password = _link(capsys, "alice")

    assert main(["publish"]) == 0

    site = _published(remote)
    assert set(site) == {".nojekyll", "index.html", "robots.txt", f"{share_id}/index.html"}
    page = site[f"{share_id}/index.html"]
    assert "WOLT" not in page and "Alice" not in page  # nothing readable without the password
    sealed = json.loads(re.search(r'id="payload"[^>]*>(.*?)</script>', page, re.S).group(1))
    report = unseal(sealed, password).decode()
    assert "Alice" in report and '"mode":"user"' in report and "WOLT" in report


def test_publish_pushes_only_changes(remote: Path, capsys: pytest.CaptureFixture[str]) -> None:
    old_id, _ = _link(capsys, "alice")
    main(["publish"])
    capsys.readouterr()

    main(["publish"])
    assert "Nothing changed" in capsys.readouterr().out

    new_id, _ = _link(capsys, "alice")  # a new link replaces the old page
    main(["publish"])
    assert f"{new_id}/index.html" in _published(remote)
    assert f"{old_id}/index.html" not in _published(remote)

    main(["user", "share", "alice", "--off"])
    main(["publish"])
    assert set(_published(remote)) == {".nojekyll", "index.html", "robots.txt"}


def test_publish_needs_a_remote(home: Path, capsys: pytest.CaptureFixture[str]) -> None:
    main(["init"])

    assert main(["publish"]) == 1
    assert "PKOSTAT_PUBLISH_REMOTE" in capsys.readouterr().err


@pytest.fixture
def client(remote: Path) -> Iterator[TestClient]:
    with TestClient(create_app(load_settings(), {"testserver"})) as test_client:
        yield test_client


def test_share_from_the_users_page(client: TestClient, remote: Path) -> None:
    response = client.post("/api/users/bob/share", headers=OURS)

    assert response.json()["ok"] is True
    assert "опубликовано отчётов: 1" in response.json()["message"]
    users = re.search(r'id="data">(.*?)</script>', client.get("/").text, re.S).group(1)
    bob = next(u for u in json.loads(users)["admin"]["users"] if u["name"] == "bob")
    assert bob["share_link"].startswith("https://example.org/site/")

    response = client.post("/api/users/bob/share/delete", headers=OURS)
    assert "Доступ по ссылке закрыт" in response.json()["message"]
    assert set(_published(remote)) == {".nojekyll", "index.html", "robots.txt"}
