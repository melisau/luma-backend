import hashlib
import secrets
from datetime import datetime, timedelta, timezone

import bcrypt
import jwt

from app.core.config import get_settings

ALGORITHM = "HS256"
# bcrypt only uses the first 72 bytes; passlib truncated silently, so existing hashes match this.
BCRYPT_MAX_BYTES = 72


def generate_event_token() -> str:
    return secrets.token_urlsafe(24)


def _password_bytes(password: str) -> bytes:
    return password.encode("utf-8")[:BCRYPT_MAX_BYTES]


def hash_password(password: str) -> str:
    return bcrypt.hashpw(_password_bytes(password), bcrypt.gensalt()).decode("ascii")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    try:
        return bcrypt.checkpw(_password_bytes(plain_password), hashed_password.encode("ascii"))
    except (ValueError, TypeError):
        return False


def create_admin_token(subject: str, token_version: int) -> str:
    settings = get_settings()
    expire = datetime.now(timezone.utc) + timedelta(minutes=30)
    payload = {"sub": subject, "ver": token_version, "exp": expire, "scope": "admin"}
    return jwt.encode(payload, settings.secret_key, algorithm=ALGORITHM)


def decode_admin_token(token: str) -> tuple[str, int] | None:
    settings = get_settings()
    try:
        payload = jwt.decode(token, settings.secret_key, algorithms=[ALGORITHM])
        subject = payload.get("sub")
        version = payload.get("ver")
        if (
            payload.get("scope") != "admin"
            or not isinstance(subject, str)
            or not subject
            or type(version) is not int
        ):
            return None
        return subject, version
    except jwt.PyJWTError:
        return None


def mask_token(token: str) -> str:
    if len(token) <= 8:
        return "***"
    return f"{token[:4]}...{token[-4:]}"


def sha256_hex(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()
