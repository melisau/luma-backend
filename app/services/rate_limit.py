import time
import hashlib
import uuid
from datetime import datetime, timedelta, timezone
from collections import defaultdict, deque

from fastapi import HTTPException, status

from app.core.config import get_settings


def _too_many(detail: str, retry_after: float) -> HTTPException:
    """429 with a Retry-After hint so clients (the photo uploader) can wait and retry by themselves."""
    seconds = max(1, min(60, int(retry_after + 0.999)))
    return HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail=detail,
                         headers={"Retry-After": str(seconds)})


def _seconds_until_free(oldest, window_seconds: int) -> float:
    if oldest is None:
        return window_seconds
    if isinstance(oldest, str):
        oldest = datetime.fromisoformat(oldest)
    if oldest.tzinfo is None:
        oldest = oldest.replace(tzinfo=timezone.utc)
    return window_seconds - (datetime.now(timezone.utc) - oldest).total_seconds()


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
            raise _too_many(detail or "Çok fazla yükleme denemesi. Lütfen biraz bekleyin.",
                            window_seconds - (now - bucket[0]))
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
                oldest=db.execute(text("SELECT MIN(created_at) FROM rate_limit_events WHERE bucket_key=:key AND created_at>=:cutoff"),{"key":key,"cutoff":cutoff}).scalar_one()
                db.rollback()
                raise _too_many(detail or "Çok fazla istek. Lütfen biraz bekleyin.", _seconds_until_free(oldest, window_seconds))
            db.execute(text("INSERT INTO rate_limit_events (id,bucket_key,created_at) VALUES (:id,:key,:now)"),{"id":str(uuid.uuid4()),"key":key,"now":datetime.now(timezone.utc)});db.commit()
        finally: db.close()


upload_rate_limiter = RateLimiter()
login_rate_limiter = RateLimiter()
message_rate_limiter = RateLimiter()


UPLOAD_BUSY_DETAIL = "Şu anda çok sayıda fotoğraf yükleniyor. Birkaç saniye sonra yeniden deneyin."


def enforce_upload_rate_limit(client_ip: str, event_token: str) -> None:
    """Each request is one batch of photos. At a wedding most guests share the venue Wi-Fi, so they
    arrive from one IP: the per-IP limit has to carry a whole crowd, and the per-event limit is a
    ceiling against abuse of one invitation link (MAX_PHOTOS_PER_EVENT still caps the total)."""
    settings = get_settings()
    upload_rate_limiter.check(f"ip:{client_ip}", settings.uploads_per_minute, detail=UPLOAD_BUSY_DETAIL)
    upload_rate_limiter.check(f"event:{event_token}", settings.event_uploads_per_minute, detail=UPLOAD_BUSY_DETAIL)


def enforce_login_rate_limit(client_ip: str) -> None:
    settings = get_settings()
    login_rate_limiter.check(
        f"login:{client_ip}",
        settings.logins_per_minute,
        detail="Çok fazla giriş denemesi. Lütfen biraz bekleyin.",
    )


register_rate_limiter = RateLimiter()


def enforce_register_rate_limit(client_ip: str) -> None:
    register_rate_limiter.check(
        f"register:{client_ip}",
        get_settings().registrations_per_hour,
        window_seconds=3600,
        detail="Bu ağdan çok fazla hesap açıldı. Lütfen daha sonra tekrar deneyin.",
    )


def owner_can_reach_guests(event) -> bool:
    """Unverified owners cannot publish invitations or email guests when verification is required."""
    if not get_settings().email_verification_required:
        return True
    owner = getattr(event, "admin", None)
    return bool(owner and owner.email_verified_at)


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
