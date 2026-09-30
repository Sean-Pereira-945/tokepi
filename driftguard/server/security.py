"""Password hashing, session tokens, and project API keys."""

from __future__ import annotations

import base64
import hashlib
import hmac
import secrets
from datetime import datetime, timedelta, timezone

import jwt

API_KEY_PREFIX = "dg_live_"
_SCRYPT_N, _SCRYPT_R, _SCRYPT_P, _SCRYPT_LEN = 2**14, 8, 1, 64
_JWT_ALGORITHM = "HS256"


def _b64(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode().rstrip("=")


def _unb64(text: str) -> bytes:
    return base64.urlsafe_b64decode(text + "=" * (-len(text) % 4))


def hash_password(password: str) -> str:
    """Hash a password with scrypt and a random salt. Returns a self-describing string."""
    salt = secrets.token_bytes(16)
    digest = hashlib.scrypt(password.encode(), salt=salt, n=_SCRYPT_N, r=_SCRYPT_R, p=_SCRYPT_P, dklen=_SCRYPT_LEN)
    return f"scrypt${_SCRYPT_N}${_SCRYPT_R}${_SCRYPT_P}${_b64(salt)}${_b64(digest)}"


def verify_password(password: str, encoded: str | None) -> bool:
    """Check a password against :func:`hash_password` output in constant time."""
    if not encoded:
        # Burn comparable CPU so a missing account is not distinguishable by timing.
        hashlib.scrypt(b"x", salt=b"0" * 16, n=_SCRYPT_N, r=_SCRYPT_R, p=_SCRYPT_P, dklen=_SCRYPT_LEN)
        return False
    try:
        scheme, n, r, p, salt, digest = encoded.split("$")
        if scheme != "scrypt":
            return False
        expected = _unb64(digest)
        actual = hashlib.scrypt(password.encode(), salt=_unb64(salt), n=int(n), r=int(r), p=int(p), dklen=len(expected))
    except (ValueError, TypeError):
        return False
    return hmac.compare_digest(actual, expected)


def generate_api_key() -> str:
    """Create a new project API key (``dg_live_`` + 43 random URL-safe characters)."""
    return API_KEY_PREFIX + secrets.token_urlsafe(32)


def hash_api_key(api_key: str) -> str:
    """Hash an API key for storage. Keys are high-entropy, so SHA-256 is sufficient."""
    return hashlib.sha256(api_key.encode()).hexdigest()


def api_key_hint(api_key: str) -> str:
    """Return a displayable, non-secret prefix of an API key."""
    return api_key[: len(API_KEY_PREFIX) + 4]


def create_session_token(account_id: str, secret: str, ttl_hours: int) -> tuple[str, str, datetime]:
    """Issue a signed session token. Returns ``(token, jti, expires_at)``."""
    jti = secrets.token_urlsafe(16)
    now = datetime.now(timezone.utc)
    expires_at = now + timedelta(hours=ttl_hours)
    token = jwt.encode({"sub": account_id, "jti": jti, "iat": now, "exp": expires_at}, secret, algorithm=_JWT_ALGORITHM)
    return token, jti, expires_at


def decode_session_token(token: str, secret: str) -> tuple[str, str]:
    """Verify a session token's signature and expiry. Returns ``(account_id, jti)``.

    Raises :class:`jwt.InvalidTokenError` (including expiry) on failure.
    """
    payload = jwt.decode(token, secret, algorithms=[_JWT_ALGORITHM], options={"require": ["sub", "jti", "exp"]})
    return str(payload["sub"]), str(payload["jti"])
