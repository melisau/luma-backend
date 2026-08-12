import re
import unicodedata
from datetime import datetime

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.core.security import generate_event_token
from app.db.models import Event
from app.schemas.event import EventCreateAdmin, EventUpdateAdmin


def slugify_name(name: str) -> str:
    normalized = unicodedata.normalize("NFD", name)
    stripped = "".join(char for char in normalized if unicodedata.category(char) != "Mn")
    slug = re.sub(r"[^a-z0-9]+", "-", stripped.lower()).strip("-")
    return (slug[:64] or "etkinlik")


def unique_slug(db: Session, base_slug: str) -> str:
    slug = base_slug
    counter = 2
    while db.query(Event).filter(Event.slug == slug).first():
        suffix = f"-{counter}"
        slug = f"{base_slug[: max(1, 64 - len(suffix))]}{suffix}"
        counter += 1
    return slug


def event_to_admin(event: Event):
    from app.schemas.event import EventAdmin

    return EventAdmin(
        name=event.name,
        slug=event.slug,
        is_active=event.is_active,
        uploads_enabled=event.uploads_enabled,
        created_at=event.created_at,
        event_date=event.event_date,
        venue=event.venue or "",
        city=event.city or "",
        private_token=event.private_token,
        invite_path=f"/e/{event.private_token}",
    )


def create_event_admin(db: Session, payload: EventCreateAdmin) -> Event:
    base_slug = payload.slug.strip() if payload.slug else slugify_name(payload.name)
    slug = unique_slug(db, slugify_name(base_slug))
    event = Event(
        name=payload.name.strip(),
        slug=slug,
        private_token=generate_event_token(),
        event_date=payload.event_date,
        venue=payload.venue.strip() if payload.venue else "",
        city=payload.city.strip() if payload.city else "",
        tagline=payload.tagline.strip() if payload.tagline else "",
        story_title=payload.story_title.strip() if payload.story_title else "",
        story_text=payload.story_text.strip() if payload.story_text else "",
        guest_note=payload.guest_note.strip() if payload.guest_note else "",
        uploads_enabled=payload.uploads_enabled,
        is_active=payload.is_active,
    )
    db.add(event)
    db.commit()
    db.refresh(event)
    return event


def update_event_admin(db: Session, event: Event, payload: EventUpdateAdmin) -> Event:
    data = payload.model_dump(exclude_unset=True)
    if "slug" in data and data["slug"]:
        candidate = slugify_name(data["slug"])
        conflict = (
            db.query(Event)
            .filter(Event.slug == candidate, Event.id != event.id)
            .first()
        )
        if conflict:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Bu slug zaten kullanılıyor.")
        event.slug = candidate
        data.pop("slug")
    for key, value in data.items():
        if key == "name" and value is not None:
            event.name = value.strip()
        elif key in {"venue", "city", "tagline", "story_title", "story_text", "guest_note"} and value is not None:
            setattr(event, key, value.strip())
        else:
            setattr(event, key, value)
    db.commit()
    db.refresh(event)
    return event


def delete_event_admin(db: Session, event: Event) -> None:
    from app.services.storage import get_storage

    storage = get_storage()
    for photo in list(event.photos):
        try:
            storage.delete(photo.storage_key_original)
            if photo.storage_key_thumb:
                storage.delete(photo.storage_key_thumb)
        except Exception:
            pass
    if event.cover_storage_key:
        try:
            storage.delete(event.cover_storage_key)
        except Exception:
            pass
    if event.music_storage_key:
        try:
            storage.delete(event.music_storage_key)
        except Exception:
            pass
    db.delete(event)
    db.commit()


def parse_event_date(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
