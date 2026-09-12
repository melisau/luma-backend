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
    email_verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)

    contacts: Mapped[list["Contact"]] = relationship(back_populates="admin", cascade="all, delete-orphan")
    events: Mapped[list["Event"]] = relationship(back_populates="admin", cascade="all, delete-orphan")


class Event(Base):
    signature_text: Mapped[str] = mapped_column(String(255), default="", server_default="")
    memory_title: Mapped[str] = mapped_column(String(255), default="Gözünden bizim hikâyemiz.", server_default="Gözünden bizim hikâyemiz.")
    memory_text: Mapped[str] = mapped_column(Text, default="O gece yakaladığın en güzel anları bizimle paylaş. Her kare, yıllarca saklayacağımız bir hatıraya dönüşsün.", server_default="")
    memory_cover_storage_key: Mapped[str | None] = mapped_column(Text, nullable=True)
    language: Mapped[str] = mapped_column(String(8), default="tr", server_default="tr")
    design_theme: Mapped[str] = mapped_column(String(32), default="romantic", server_default="romantic")
    publish_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    rsvp_reminder_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    rsvp_reminder_sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    memory_delete_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    memory_purged_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    access_code_hash: Mapped[str | None] = mapped_column(String(255), nullable=True)
    album_public: Mapped[bool] = mapped_column(Boolean, default=True, server_default="1")
    __tablename__ = "events"
    __table_args__ = (UniqueConstraint("admin_id", "slug", name="uq_admin_event_slug"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    admin_id: Mapped[str] = mapped_column(String(36), ForeignKey("admin_users.id"), index=True)
    name: Mapped[str] = mapped_column(String(255))
    slug: Mapped[str] = mapped_column(String(128), index=True)
    private_token: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    uploads_enabled: Mapped[bool] = mapped_column(Boolean, default=True)

    event_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    venue: Mapped[str] = mapped_column(String(255), default="")
    city: Mapped[str] = mapped_column(String(255), default="")
    envelope_color: Mapped[str] = mapped_column(String(7), default="#e9dcc4", server_default="#e9dcc4")
    seal_color: Mapped[str] = mapped_column(String(7), default="#873f43", server_default="#873f43")
    paper_color: Mapped[str] = mapped_column(String(7), default="#fffdf7", server_default="#fffdf7")
    envelope_texture: Mapped[str] = mapped_column(String(20), default="linen", server_default="linen")
    envelope_pattern: Mapped[str] = mapped_column(String(20), default="plain", server_default="plain")
    seal_motif: Mapped[str] = mapped_column(String(20), default="botanical", server_default="botanical")
    address: Mapped[str] = mapped_column(Text, default="", server_default="")
    transport_notes: Mapped[str] = mapped_column(Text, default="", server_default="")
    contact_info: Mapped[str] = mapped_column(Text, default="", server_default="")
    schedule: Mapped[str] = mapped_column(Text, default="", server_default="")
    opening_style: Mapped[str] = mapped_column(String(32), default="classic", server_default="classic")
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
    admin: Mapped[AdminUser] = relationship(back_populates="events")
    members: Mapped[list["EventMember"]] = relationship(back_populates="event", cascade="all, delete-orphan")


class Guest(Base):
    rsvp_token_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    __tablename__ = "guests"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    event_id: Mapped[str] = mapped_column(String(36), ForeignKey("events.id"), index=True)
    name: Mapped[str] = mapped_column(String(255))
    email: Mapped[str] = mapped_column(String(255), index=True)
    status: Mapped[str] = mapped_column(String(32), default=GuestStatus.PENDING.value, index=True)
    people: Mapped[int] = mapped_column(Integer, default=1)
    dietary_requirements: Mapped[str] = mapped_column(Text, default="", server_default="")
    notes: Mapped[str] = mapped_column(Text, default="", server_default="")
    group_name: Mapped[str] = mapped_column(String(255), default="", server_default="")
    table_name: Mapped[str] = mapped_column(String(255), default="", server_default="")
    source: Mapped[str] = mapped_column(String(32), default=GuestSource.ADMIN.value)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    responded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    event: Mapped[Event] = relationship(back_populates="guests")

    __table_args__ = (UniqueConstraint("event_id", "email", name="uq_event_guest_email"),)


class EventMember(Base):
    __tablename__ = "event_members"
    __table_args__ = (UniqueConstraint("event_id", "admin_id", name="uq_event_member_admin"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    event_id: Mapped[str] = mapped_column(String(36), ForeignKey("events.id"), index=True)
    admin_id: Mapped[str] = mapped_column(String(36), ForeignKey("admin_users.id"), index=True)
    role: Mapped[str] = mapped_column(String(16), default="viewer")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)

    event: Mapped[Event] = relationship(back_populates="members")
    admin: Mapped[AdminUser] = relationship()


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
    content_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    __table_args__ = (UniqueConstraint("event_id", "content_hash", name="uq_event_photo_hash"),)
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


class AccountToken(Base):
    __tablename__ = "account_tokens"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    admin_id: Mapped[str] = mapped_column(String(36), ForeignKey("admin_users.id"), index=True)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    purpose: Mapped[str] = mapped_column(String(24), index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    admin: Mapped[AdminUser] = relationship()

class RateLimitEvent(Base):
    __tablename__="rate_limit_events"
    id: Mapped[str]=mapped_column(String(36),primary_key=True)
    bucket_key: Mapped[str]=mapped_column(String(255),index=True)
    created_at: Mapped[datetime]=mapped_column(DateTime(timezone=True),index=True,default=utc_now)
