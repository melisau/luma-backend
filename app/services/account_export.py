"""Everything an account owner can request about themselves (KVKK m.11), as one JSON document."""
from datetime import date, datetime, timezone
from decimal import Decimal

from sqlalchemy.orm import Session

from app.db.models import AdminUser, Contact, Event, EventMember

# Secrets and internal plumbing never leave the server, even to the owner.
_HIDDEN = {"id", "password_hash", "token_version", "private_token", "content_hash"}


def _hidden(column: str) -> bool:
    return (
        column in _HIDDEN
        or column.endswith("_id")
        or column.endswith("_hash")
        or "storage_key" in column
    )


def _value(value):
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, Decimal):
        return float(value)
    return value


def _row(obj) -> dict:
    return {
        column.name: _value(getattr(obj, column.key))
        for column in obj.__table__.columns
        if not _hidden(column.name)
    }


def _event(event: Event) -> dict:
    data = _row(event)
    data["guests"] = [_row(guest) for guest in event.guests]
    data["guestbook_messages"] = [_row(message) for message in event.messages]
    # Photo files are in the event's album ZIP; this lists what exists.
    data["photos"] = [_row(photo) for photo in event.photos]
    data["activity"] = [_row(item) for item in event.activities]
    data["team"] = [
        {"email": member.admin.email, "role": member.role, "created_at": _value(member.created_at)}
        for member in event.members
    ]
    return data


def export_account(db: Session, admin: AdminUser) -> dict:
    owned = db.query(Event).filter(Event.admin_id == admin.id).order_by(Event.created_at).all()
    memberships = db.query(EventMember).filter(EventMember.admin_id == admin.id).all()
    contacts = db.query(Contact).filter(Contact.admin_id == admin.id).order_by(Contact.created_at).all()
    return {
        "service": "Luma Event (https://luma.melisauyar.com)",
        "exported_at": datetime.now(timezone.utc).isoformat(),
        "note": "Hesabınıza ait kişisel veriler (KVKK m.11). Fotoğraf dosyaları her etkinliğin albüm ZIP'inde indirilebilir.",
        "account": _row(admin),
        "contacts": [_row(contact) for contact in contacts],
        "events": [_event(event) for event in owned],
        "team_memberships": [
            {"event_name": member.event.name, "role": member.role, "created_at": _value(member.created_at)}
            for member in memberships
        ],
    }
