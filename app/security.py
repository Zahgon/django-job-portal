"""Password storage and bearer tokens.

Stored passwords keep the ``pbkdf2_sha256$<iterations>$<salt>$<hash>`` encoding
the previous stack wrote, so every account that existed before the migration
still signs in, and the iteration count is read back out of the stored string
rather than assumed.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import secrets
import time
from typing import Any

ALGORITHM = "pbkdf2_sha256"
ITERATIONS = 870000
SALT_ALPHABET = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"
SALT_LENGTH = 22
UNUSABLE_PREFIX = "!"
UNUSABLE_LENGTH = 40


def random_string(length: int, alphabet: str = SALT_ALPHABET) -> str:
    return "".join(secrets.choice(alphabet) for _ in range(length))


def encode(password: str, salt: str, iterations: int = ITERATIONS) -> str:
    """Encode one password with a known salt; the format is part of the contract."""
    if "$" in salt:
        raise ValueError("salt must not contain $")
    digest = hashlib.pbkdf2_hmac(
        "sha256", password.encode("utf-8"), salt.encode("utf-8"), iterations
    )
    return "%s$%d$%s$%s" % (
        ALGORITHM,
        iterations,
        salt,
        base64.b64encode(digest).decode("ascii").strip(),
    )


def make_password(password: str | None) -> str:
    """Hash a password, or mint an unusable one when there is no password."""
    if password is None:
        return UNUSABLE_PREFIX + random_string(UNUSABLE_LENGTH)
    return encode(password, random_string(SALT_LENGTH))


def is_password_usable(encoded: str | None) -> bool:
    return encoded is None or not encoded.startswith(UNUSABLE_PREFIX)


def check_password(password: str | None, encoded: str | None) -> bool:
    """Verify a password against a stored hash, in constant time."""
    if password is None or not encoded or not is_password_usable(encoded):
        return False
    try:
        algorithm, iterations, salt, _ = encoded.split("$", 3)
    except ValueError:
        return False
    if algorithm != ALGORITHM:
        return False
    try:
        candidate = encode(password, salt, int(iterations))
    except (TypeError, ValueError):
        return False
    return hmac.compare_digest(candidate.encode("utf-8"), encoded.encode("utf-8"))


# ------------------------------------------------------------------ tokens ---
def _b64url(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")


def _unb64url(value: str) -> bytes:
    padding = "=" * (-len(value) % 4)
    return base64.urlsafe_b64decode(value + padding)


class TokenError(Exception):
    """A bearer token that cannot be trusted."""


def sign_token(payload: dict[str, Any], secret: str) -> str:
    """Produce a compact HS256 token carrying the given claims."""
    header = _b64url(json.dumps({"alg": "HS256", "typ": "JWT"},
                                separators=(",", ":")).encode("utf-8"))
    body = _b64url(json.dumps(payload, separators=(",", ":"),
                              sort_keys=False).encode("utf-8"))
    signing_input = ("%s.%s" % (header, body)).encode("ascii")
    signature = hmac.new(secret.encode("utf-8"), signing_input,
                         hashlib.sha256).digest()
    return "%s.%s.%s" % (header, body, _b64url(signature))


def read_token(token: str, secret: str, verify_expiry: bool = True) -> dict[str, Any]:
    """Return the claims of a token, raising ``TokenError`` when it is not valid."""
    try:
        header, body, signature = token.split(".")
    except (AttributeError, ValueError) as exc:
        raise TokenError("token is not well formed") from exc
    signing_input = ("%s.%s" % (header, body)).encode("ascii")
    expected = hmac.new(secret.encode("utf-8"), signing_input,
                        hashlib.sha256).digest()
    try:
        given = _unb64url(signature)
    except Exception as exc:  # noqa: BLE001 - any decoding failure is a bad token
        raise TokenError("token signature is not readable") from exc
    if not hmac.compare_digest(expected, given):
        raise TokenError("token signature does not match")
    try:
        claims = json.loads(_unb64url(body))
    except Exception as exc:  # noqa: BLE001 - any decoding failure is a bad token
        raise TokenError("token payload is not readable") from exc
    if verify_expiry and claims.get("exp") is not None:
        if float(claims["exp"]) <= time.time():
            raise TokenError("token has expired")
    return claims
