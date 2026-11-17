"""Slide show of an event's photos (venue screen, and optionally guests).

Only APPROVED photos can ever be in it, so a guest's upload (venue QR or personal link) appears only
after the owner approves it. The owner curates the order: `photo_ids` is the order they saved;
approved photos they did not keep are remembered in `removed_ids`. With `auto_add` on, photos
approved later join at the end, so the screen at the venue keeps up during the event.
"""
from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from app.db.models import Event, Photo, PhotoStatus

TRANSITIONS = ("fade", "slide", "zoom", "mix")
DEFAULTS: dict[str, Any] = {
    "photo_ids": [],
    "removed_ids": [],
    "auto_add": True,
    "transition": "fade",
    "seconds": 6,
    "show_to_guests": True,
    "show_captions": True,
    "title": "",
}


def settings(event: Event) -> dict[str, Any]:
    stored = event.slideshow if isinstance(event.slideshow, dict) else {}
    return {**DEFAULTS, **{key: stored[key] for key in DEFAULTS if key in stored}}


def _approved(db: Session, event: Event) -> list[Photo]:
    return (
        db.query(Photo)
        .filter(Photo.event_id == event.id, Photo.status == PhotoStatus.APPROVED.value)
        .order_by(Photo.created_at.asc())
        .all()
    )


def slides(db: Session, event: Event) -> list[Photo]:
    """The photos on screen, in order."""
    config = settings(event)
    approved = _approved(db, event)
    by_id = {photo.id: photo for photo in approved}
    chosen = [by_id[pid] for pid in config["photo_ids"] if pid in by_id]
    if config["auto_add"]:
        taken = set(config["photo_ids"]) | set(config["removed_ids"])
        chosen += [photo for photo in approved if photo.id not in taken]
    return chosen


def available(db: Session, event: Event, current: list[Photo]) -> list[Photo]:
    on_screen = {photo.id for photo in current}
    return [photo for photo in _approved(db, event) if photo.id not in on_screen]


def save(db: Session, event: Event, data: dict[str, Any]) -> None:
    """`photo_ids` is the full order the owner wants; any approved photo left out is 'removed', so
    auto_add does not bring it back."""
    config = settings(event)
    approved_ids = {photo.id for photo in _approved(db, event)}
    if "photo_ids" not in data:
        # Keep what is on screen now (including photos auto_add brought in), e.g. when auto_add
        # is switched off, the show must not lose them.
        data = {**data, "photo_ids": [photo.id for photo in slides(db, event)]}
    if "photo_ids" in data:
        order = []
        for pid in data["photo_ids"]:
            if pid in approved_ids and pid not in order:
                order.append(pid)
        config["photo_ids"] = order
        config["removed_ids"] = sorted(approved_ids - set(order))
    for key in ("auto_add", "show_to_guests", "show_captions"):
        if key in data and data[key] is not None:
            config[key] = bool(data[key])
    if data.get("transition") in TRANSITIONS:
        config["transition"] = data["transition"]
    if data.get("seconds") is not None:
        config["seconds"] = max(3, min(15, int(data["seconds"])))
    if data.get("title") is not None:
        config["title"] = str(data["title"]).strip()[:120]
    event.slideshow = config
    db.commit()


def guests_can_watch(event: Event) -> bool:
    # "Share approved photos with guests" (album_public) is the master switch for guests.
    return bool(event.album_public) and settings(event)["show_to_guests"]


def contains(db: Session, event: Event, photo_id: str) -> bool:
    return any(photo.id == photo_id for photo in slides(db, event))
