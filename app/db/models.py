import enum
import uuid
from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.database import Base


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class PhotoStatus(str, enum.Enum):
    UPLOADED = "uploaded"
    APPROVED = "approved"
    HIDDEN = "hidden"
    DELETED = "deleted"


class GuestStatus(str, enum.Enum):
    ATTENDING = "attending"
    DECLINED = "declined"
    PENDING = "pending"


class GuestSource(str, enum.Enum):
    ADMIN = "admin"
    EXTERNAL = "external"


class MessageStatus(str, enum.Enum):
    PENDING = "pending"
    APPROVED = "approved"
    HIDDEN = "hidden"


class AdminUser(Base):
    __tablename__ = "admin_users"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    display_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)

    contacts: Mapped[list["Contact"]] = relationship(back_populates="admin", cascade="all, delete-orphan")


class Event(Base):
    __tablename__ = "events"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name: Mapped[str] = mapped_column(String(255))
    slug: Mapped[str] = mapped_column(String(128), index=True)
    private_token: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    uploads_enabled: Mapped[bool] = mapped_column(Boolean, default=True)

    event_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    venue: Mapped[str] = mapped_column(String(255), default="")
    city: Mapped[str] = mapped_column(String(255), default="")
    tagline: Mapped[str] = mapped_column(String(512), default="")
    story_title: Mapped[str] = mapped_column(String(512), default="")
    story_text: Mapped[str] = mapped_column(Text, default="")
    guest_note: Mapped[str] = mapped_column(Text, default="")
    cover_storage_key: Mapped[str | None] = mapped_column(Text, nullable=True)
    music_storage_key: Mapped[str | None] = mapped_column(Text, nullable=True)
    music_filename: Mapped[str | None] = mapped_column(String(512), nullable=True)
    music_mime_type: Mapped[str | None] = mapped_column(String(128), nullable=True)

    photos: Mapped[list["Photo"]] = relationship(back_populates="event", cascade="all, delete-orphan")
    guests: Mapped[list["Guest"]] = relationship(back_populates="event", cascade="all, delete-orphan")
    messages: Mapped[list["GuestbookMessage"]] = relationship(
        back_populates="event", cascade="all, delete-orphan"
    )
    activities: Mapped[list["EventActivity"]] = relationship(
        back_populates="event", cascade="all, delete-orphan"
    )


class Guest(Base):
    __tablename__ = "guests"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    event_id: Mapped[str] = mapped_column(String(36), ForeignKey("events.id"), index=True)
    name: Mapped[str] = mapped_column(String(255))
    email: Mapped[str] = mapped_column(String(255), index=True)
    status: Mapped[str] = mapped_column(String(32), default=GuestStatus.PENDING.value, index=True)
    people: Mapped[int] = mapped_column(Integer, default=1)
    source: Mapped[str] = mapped_column(String(32), default=GuestSource.ADMIN.value)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    responded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    event: Mapped[Event] = relationship(back_populates="guests")

    __table_args__ = (UniqueConstraint("event_id", "email", name="uq_event_guest_email"),)


class GuestbookMessage(Base):
    __tablename__ = "guestbook_messages"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    event_id: Mapped[str] = mapped_column(String(36), ForeignKey("events.id"), index=True)
    name: Mapped[str] = mapped_column(String(255))
    message: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(32), default=MessageStatus.PENDING.value, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)

    event: Mapped[Event] = relationship(back_populates="messages")


class Contact(Base):
    __tablename__ = "contacts"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    admin_id: Mapped[str] = mapped_column(String(36), ForeignKey("admin_users.id"), index=True)
    name: Mapped[str] = mapped_column(String(255))
    email: Mapped[str] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)

    admin: Mapped[AdminUser] = relationship(back_populates="contacts")

    __table_args__ = (UniqueConstraint("admin_id", "email", name="uq_admin_contact_email"),)


class Photo(Base):
    __tablename__ = "photos"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    event_id: Mapped[str] = mapped_column(String(36), ForeignKey("events.id"), index=True)
    storage_key_original: Mapped[str] = mapped_column(Text)
    storage_key_thumb: Mapped[str | None] = mapped_column(Text, nullable=True)
    original_filename: Mapped[str | None] = mapped_column(String(512), nullable=True)
    mime_type: Mapped[str] = mapped_column(String(64))
    size: Mapped[int] = mapped_column(Integer)
    width: Mapped[int] = mapped_column(Integer)
    height: Mapped[int] = mapped_column(Integer)
    uploader_name: Mapped[str] = mapped_column(String(255))
    caption: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(String(32), default=PhotoStatus.UPLOADED.value, index=True)
    favorite: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)

    event: Mapped[Event] = relationship(back_populates="photos")

    __table_args__ = (UniqueConstraint("event_id", "id", name="uq_event_photo"),)


class EventActivity(Base):
    __tablename__ = "event_activities"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    event_id: Mapped[str] = mapped_column(String(36), ForeignKey("events.id"), index=True)
    text: Mapped[str] = mapped_column(String(512))
    kind: Mapped[str] = mapped_column(String(32), default="check", index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)

    event: Mapped[Event] = relationship(back_populates="activities")
