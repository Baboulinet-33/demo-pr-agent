import hashlib
import hmac
import os
import secrets
from datetime import datetime, timedelta, timezone
from typing import Optional

import jwt

JWT_ALGORITHM = "HS256"
TOKEN_TTL_MINUTES = 60
PBKDF2_ITERATIONS = 100_000


def _secret() -> str:
    """Return the JWT signing secret from the environment."""
    return os.environ.get("JWT_SECRET", "dev-only-secret-change-me-0123456789abcdef")


def hash_password(password: str) -> str:
    salt = secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), PBKDF2_ITERATIONS)
    return f"pbkdf2_sha256${salt}${digest.hex()}"


def verify_password(password: str, stored: str) -> bool:
    try:
        _, salt, expected = stored.split("$", 2)
    except ValueError:
        return False
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), PBKDF2_ITERATIONS)
    return hmac.compare_digest(digest.hex(), expected)


def create_access_token(subject: str) -> str:
    now = datetime.now(timezone.utc)
    payload = {"sub": subject, "iat": now, "exp": now + timedelta(minutes=TOKEN_TTL_MINUTES)}
    return jwt.encode(payload, _secret(), algorithm=JWT_ALGORITHM)


def decode_access_token(token: str) -> Optional[str]:
    try:
        payload = jwt.decode(token, _secret(), algorithms=[JWT_ALGORITHM])
    except jwt.PyJWTError:
        return None
    subject = payload.get("sub")
    return subject if isinstance(subject, str) else None


REPORT_TOKEN_TTL_MINUTES = 60 * 24  # one day: export links outlive the session token


def create_report_token(subject: str) -> str:
    """Sign a long-lived token meant to be embedded in export URLs."""
    now = datetime.now(timezone.utc)
    payload = {
        "sub": subject,
        "purpose": "report",
        "iat": now,
        "exp": now + timedelta(minutes=REPORT_TOKEN_TTL_MINUTES),
    }
    return jwt.encode(payload, _secret(), algorithm=JWT_ALGORITHM)


def decode_report_token(token: str) -> Optional[str]:
    """Return the token subject, or ``None`` when the token is invalid."""
    try:
        payload = jwt.decode(token, _secret(), algorithms=[JWT_ALGORITHM])
    except jwt.PyJWTError:
        return None
    subject = payload.get("sub")
    return subject if isinstance(subject, str) else None
