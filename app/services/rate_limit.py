import time
from collections import defaultdict, deque

from fastapi import HTTPException, status

from app.core.config import get_settings


class RateLimiter:
    def __init__(self) -> None:
        self._events: dict[str, deque[float]] = defaultdict(deque)

    def check(self, key: str, limit: int, window_seconds: int = 60, detail: str | None = None) -> None:
        now = time.monotonic()
        bucket = self._events[key]
        while bucket and now - bucket[0] > window_seconds:
            bucket.popleft()
        if len(bucket) >= limit:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=detail or "Çok fazla yükleme denemesi. Lütfen biraz bekleyin.",
            )
        bucket.append(now)


upload_rate_limiter = RateLimiter()
login_rate_limiter = RateLimiter()
message_rate_limiter = RateLimiter()


def enforce_upload_rate_limit(client_ip: str, event_token: str) -> None:
    settings = get_settings()
    upload_rate_limiter.check(f"ip:{client_ip}", settings.uploads_per_minute)
    upload_rate_limiter.check(f"event:{event_token}", settings.uploads_per_minute * 2)


def enforce_login_rate_limit(client_ip: str) -> None:
    settings = get_settings()
    login_rate_limiter.check(
        f"login:{client_ip}",
        settings.logins_per_minute,
        detail="Çok fazla giriş denemesi. Lütfen biraz bekleyin.",
    )


def enforce_message_rate_limit(client_ip: str, event_token: str) -> None:
    settings = get_settings()
    message_rate_limiter.check(f"msg-ip:{client_ip}", settings.messages_per_minute)
    message_rate_limiter.check(f"msg-event:{event_token}", settings.messages_per_minute * 2)
