"""Sealing a report: gzip, then AES-256-GCM with a key derived from the password (PBKDF2-SHA256).

The browser undoes it with WebCrypto and DecompressionStream (publish/locked.html); the format here
and the code there must change together.
"""

import base64
import gzip
import os

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

from pkostat.errors import PkoStatError

FORMAT = 1
ITERATIONS = 310_000  # OWASP's figure for PBKDF2-SHA256; a second or less on a phone


def seal(plain: bytes, password: str, iterations: int = ITERATIONS) -> dict[str, object]:
    salt, iv = os.urandom(16), os.urandom(12)
    data = AESGCM(_key(password, salt, iterations)).encrypt(iv, gzip.compress(plain, mtime=0), None)
    return {"v": FORMAT, "iter": iterations, "salt": _b64(salt), "iv": _b64(iv), "data": _b64(data)}


def unseal(sealed: dict[str, object], password: str) -> bytes:
    """The Python twin of the browser code, for tests and for checking a published page."""
    salt, iv, data = (base64.b64decode(str(sealed[name])) for name in ("salt", "iv", "data"))
    iterations = sealed["iter"]
    assert isinstance(iterations, int)
    try:
        zipped = AESGCM(_key(password, salt, iterations)).decrypt(iv, data, None)
    except InvalidTag as exc:
        raise PkoStatError("Wrong password or damaged page.") from exc
    return gzip.decompress(zipped)


def _key(password: str, salt: bytes, iterations: int) -> bytes:
    kdf = PBKDF2HMAC(algorithm=hashes.SHA256(), length=32, salt=salt, iterations=iterations)
    return kdf.derive(password.encode("utf-8"))


def _b64(raw: bytes) -> str:
    return base64.b64encode(raw).decode("ascii")
