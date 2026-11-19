"""Pushing the site as a single commit to a branch (gh-pages), replacing whatever was there.

Every publish is a fresh one-commit history, so old encrypted reports do not pile up in the
repository. The commit is authored by "PkoStat", not by the git user of this PC.
"""

import os
import subprocess
import tempfile
from pathlib import Path

from pkostat.errors import PkoStatError

BRANCH = "gh-pages"
TIMEOUT = 120
_IDENTITY = {
    "GIT_AUTHOR_NAME": "PkoStat",
    "GIT_AUTHOR_EMAIL": "pkostat@localhost",
    "GIT_COMMITTER_NAME": "PkoStat",
    "GIT_COMMITTER_EMAIL": "pkostat@localhost",
}


def push_site(site: dict[str, bytes], remote: str, branch: str = BRANCH) -> None:
    with tempfile.TemporaryDirectory(prefix="pkostat-site-") as tmp:
        root = Path(tmp)
        for name, content in site.items():
            path = root / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(content)
        _git(root, "init", "-q", "-b", branch)
        _git(root, "add", "--", *sorted(site))
        _git(root, "commit", "-q", "-m", "Publish reports")
        _git(root, "push", "--force", "-q", remote, f"{branch}:{branch}")


def _git(cwd: Path, *args: str) -> None:
    try:
        result = subprocess.run(
            ["git", "-C", str(cwd), *args],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=TIMEOUT,
            check=False,
            env={**os.environ, **_IDENTITY},
        )
    except FileNotFoundError as exc:
        raise PkoStatError("git is not installed or not on PATH.") from exc
    except subprocess.TimeoutExpired as exc:
        raise PkoStatError(f"git {args[0]} took longer than {TIMEOUT} s.") from exc
    if result.returncode != 0:
        detail = (result.stderr or result.stdout).strip().splitlines()[-3:]
        raise PkoStatError(f"git {args[0]} failed: {' '.join(detail)}")
