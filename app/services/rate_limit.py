import time
import hashlib
import uuid
from datetime import datetime, timedelta, timezone
from collections import defaultdict, deque

from fastapi import HTTPException, status

from app.core.config import get_settings


class RateLimiter:
    def __init__(self) -> None:
        self._events: dict[str, deque[float]] = defaultdict(deque)

    def check(self, key: str, limit: int, window_seconds: int = 60, detail: str | None = None) -> None:
        if get_settings().rate_limit_backend == "database":
            return self._database_check(key, limit, window_seconds, detail)
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

    def _database_check(self, key, limit, window_seconds, detail):
        from sqlalchemy import text
        from app.db import database as db_module
        db=db_module.SessionLocal()
        try:
            if get_settings().database_url.startswith("postgresql"):
                lock=int(hashlib.sha256(key.encode()).hexdigest()[:15],16)
                db.execute(text("SELECT pg_advisory_xact_lock(:lock)"),{"lock":lock})
            cutoff=datetime.now(timezone.utc)-timedelta(seconds=window_seconds)
            db.execute(text("DELETE FROM rate_limit_events WHERE created_at < :cutoff"),{"cutoff":cutoff})
            count=db.execute(text("SELECT COUNT(*) FROM rate_limit_events WHERE bucket_key=:key AND created_at>=:cutoff"),{"key":key,"cutoff":cutoff}).scalar_one()
            if count>=limit:
                db.rollback();raise HTTPException(status_code=429,detail=detail or "Çok fazla istek. Lütfen biraz bekleyin.")
            db.execute(text("INSERT INTO rate_limit_events (id,bucket_key,created_at) VALUES (:id,:key,:now)"),{"id":str(uuid.uuid4()),"key":key,"now":datetime.now(timezone.utc)});db.commit()
        finally: db.close()


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


rsvp_rate_limiter = RateLimiter()

def enforce_rsvp_rate_limit(client_ip: str, event_token: str) -> None:
    rsvp_rate_limiter.check(
        f"rsvp:{event_token}:{client_ip}", get_settings().rsvps_per_minute,
        detail="Çok fazla katılım yanıtı gönderildi. Lütfen bir dakika sonra tekrar deneyin.",
    )
