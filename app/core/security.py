import hashlib
import secrets
from datetime import datetime, timedelta, timezone

from jose import JWTError, jwt
from passlib.context import CryptContext

from app.core.config import get_settings

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
ALGORITHM = "HS256"


def generate_event_token() -> str:
    return secrets.token_urlsafe(24)


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)


def create_admin_token(subject: str) -> str:
    settings = get_settings()
    expire = datetime.now(timezone.utc) + timedelta(hours=12)
    payload = {"sub": subject, "exp": expire, "scope": "admin"}
    return jwt.encode(payload, settings.secret_key, algorithm=ALGORITHM)


def decode_admin_token(token: str) -> str | None:
    settings = get_settings()
    try:
        payload = jwt.decode(token, settings.secret_key, algorithms=[ALGORITHM])
        if payload.get("scope") != "admin":
            return None
        return payload.get("sub")
    except JWTError:
        return None


def mask_token(token: str) -> str:
    if len(token) <= 8:
        return "***"
    return f"{token[:4]}...{token[-4:]}"


def sha256_hex(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()
