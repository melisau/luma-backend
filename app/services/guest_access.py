"""Personal invitation links (invite_mode == "personal").

A link can always be forwarded, so it is not the key on its own:
- The link carries the guest id and a token derived from SECRET_KEY, the guest id and the guest's
  invite_version. The owner can copy it again at any time; "reset" bumps the version, which kills the
  old link and forgets the guest's devices.
- The first devices that open it (as many as the guest's party, at most MAX_FREE_DEVICES) are bound
  to the guest with an httpOnly cookie. Any further device needs a 6-digit code sent to the guest's
  e-mail, so a forwarded link is useless to someone without that inbox.
- The venue QR code carries the event's upload_key: photo upload only, on the event days.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import secrets
from datetime import datetime, timedelta, timezone

from fastapi import HTTPException, Request, Response
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.models import Event, Guest, GuestDevice

MAX_FREE_DEVICES = 6
COOKIE_DAYS = 180
CODE_MINUTES = 15
CODE_RESEND_SECONDS = 60
CODE_MAX_ATTEMPTS = 5
UPLOAD_KEY_DAYS_BEFORE = 1
UPLOAD_KEY_DAYS_AFTER = 3


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _aware(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value


def is_personal(event: Event | None) -> bool:
    return bool(event and (event.invite_mode or "open") == "personal")


# --- personal link -----------------------------------------------------------------------------

def invite_token(guest: Guest) -> str:
    message = f"invite:{guest.id}:{guest.invite_version or 0}".encode()
    digest = hmac.new(get_settings().secret_key.encode(), message, hashlib.sha256).digest()
    return base64.urlsafe_b64encode(digest).decode().rstrip("=")[:32]


def invite_fragment(guest: Guest) -> str:
    """The part after '#' in the guest's link (fragments never reach servers or referrers)."""
    return f"g={guest.id}.{invite_token(guest)}"


def guest_from_link(db: Session, event: Event, guest_id: str, token: str) -> Guest | None:
    guest = db.query(Guest).filter(Guest.id == guest_id, Guest.event_id == event.id).one_or_none()
    if not guest or not hmac.compare_digest(invite_token(guest), token or ""):
        return None
    return guest


def reset_link(db: Session, guest: Guest) -> None:
    guest.invite_version = (guest.invite_version or 0) + 1
    db.query(GuestDevice).filter(GuestDevice.guest_id == guest.id).delete()
    guest.access_code_hash = None
    guest.access_code_expires_at = None
    guest.access_code_attempts = 0
    db.commit()


# --- device cookie -----------------------------------------------------------------------------

def cookie_name(event: Event) -> str:
    return "luma_guest_" + hashlib.sha256(event.id.encode()).hexdigest()[:16]


def _hash(secret: str) -> str:
    return hashlib.sha256(secret.encode()).hexdigest()


def device_allowance(guest: Guest) -> int:
    return max(1, min(guest.people or 1, MAX_FREE_DEVICES))


def bind_device(db: Session, guest: Guest, request: Request, response: Response, event: Event) -> None:
    secret = secrets.token_urlsafe(32)
    db.add(GuestDevice(guest_id=guest.id, secret_hash=_hash(secret)))
    db.commit()
    response.set_cookie(cookie_name(event), f"{guest.id}.{secret}", max_age=COOKIE_DAYS * 86400, httponly=True,
                        secure=request.url.scheme == "https", samesite="lax", path="/api")


def device_guest(db: Session, event: Event, request: Request) -> Guest | None:
    """The guest whose device cookie this request carries, if it is still valid."""
    raw = request.cookies.get(cookie_name(event), "")
    guest_id, _, secret = raw.partition(".")
    if not guest_id or not secret:
        return None
    device = (
        db.query(GuestDevice)
        .join(Guest, Guest.id == GuestDevice.guest_id)
        .filter(GuestDevice.secret_hash == _hash(secret), Guest.id == guest_id, Guest.event_id == event.id)
        .one_or_none()
    )
    if not device:
        return None
    now = utc_now()
    if not device.last_seen_at or now - _aware(device.last_seen_at) > timedelta(hours=1):
        device.last_seen_at = now
        db.commit()
    return device.guest


# --- e-mail code for a further device ---------------------------------------------------------

def email_hint(email: str) -> str:
    local, _, domain = email.partition("@")
    name, _, tld = domain.rpartition(".")
    masked_local = (local[:1] + "***") if local else "***"
    masked_domain = (name[:1] + "***") if name else "***"
    return f"{masked_local}@{masked_domain}.{tld}" if tld else f"{masked_local}@{masked_domain}"


def send_code(db: Session, event: Event, guest: Guest) -> None:
    now = utc_now()
    sent = _aware(guest.access_code_sent_at)
    if sent and (now - sent).total_seconds() < CODE_RESEND_SECONDS and _aware(guest.access_code_expires_at) and _aware(guest.access_code_expires_at) > now:
        return  # a fresh code is already on its way
    code = f"{secrets.randbelow(1_000_000):06d}"
    guest.access_code_hash = hmac.new(get_settings().secret_key.encode(), f"code:{guest.id}:{code}".encode(), hashlib.sha256).hexdigest()
    guest.access_code_expires_at = now + timedelta(minutes=CODE_MINUTES)
    guest.access_code_attempts = 0
    guest.access_code_sent_at = now
    db.commit()
    from app.services.email_service import send_email
    try:
        send_email(guest.email, f"{event.name}: davetiye kodunuz",
                   f"Davetiyenizi yeni bir cihazda açmak için kodunuz: {code}\n"
                   f"Kod {CODE_MINUTES} dakika geçerlidir. Bu isteği siz yapmadıysanız bu e-postayı yok sayın; "
                   "davetiyeniz başkasına açılmaz.")
    except Exception:
        import logging
        logging.getLogger(__name__).exception("Invitation code email failed")


def check_code(db: Session, guest: Guest, code: str) -> bool:
    expires = _aware(guest.access_code_expires_at)
    if not guest.access_code_hash or not expires or expires < utc_now():
        return False
    if (guest.access_code_attempts or 0) >= CODE_MAX_ATTEMPTS:
        return False
    expected = hmac.new(get_settings().secret_key.encode(), f"code:{guest.id}:{(code or '').strip()}".encode(), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected, guest.access_code_hash):
        guest.access_code_attempts = (guest.access_code_attempts or 0) + 1
        db.commit()
        return False
    guest.access_code_hash = None
    guest.access_code_expires_at = None
    guest.access_code_attempts = 0
    db.commit()
    return True


# --- venue QR upload key -----------------------------------------------------------------------

def ensure_upload_key(db: Session, event: Event) -> str:
    if not event.upload_key:
        event.upload_key = secrets.token_urlsafe(24)
        db.commit()
    return event.upload_key


def upload_key_valid(event: Event, key: str | None) -> bool:
    if not key or not event.upload_key or not hmac.compare_digest(event.upload_key, key):
        return False
    date = _aware(event.event_date)
    if date is None:
        return True
    now = utc_now()
    return date - timedelta(days=UPLOAD_KEY_DAYS_BEFORE) <= now <= date + timedelta(days=UPLOAD_KEY_DAYS_AFTER)


def personal_link_required() -> HTTPException:
    return HTTPException(status_code=401, detail="Bu davetiye kişiye özeldir. Lütfen size gönderilen kişisel bağlantıyı kullanın.",
                         headers={"X-Luma-Access": "personal"})
