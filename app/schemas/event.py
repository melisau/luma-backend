from app.schemas.dates import EventDateModel
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator


class EventPublic(EventDateModel):
    model_config = ConfigDict(from_attributes=True)

    name: str
    slug: str
    is_active: bool
    uploads_enabled: bool
    album_public: bool = True
    created_at: datetime
    event_date: datetime | None = None
    venue: str = ""
    city: str = ""


class EventAdmin(EventPublic):
    access_code_enabled: bool = False
    private_token: str
    invite_path: str


class EventCreateAdmin(EventDateModel):
    name: str = Field(min_length=1, max_length=255)
    slug: str | None = Field(default=None, max_length=64)
    event_date: datetime | None = None
    venue: str = ""
    city: str = ""
    tagline: str = ""
    story_title: str = ""
    story_text: str = ""
    guest_note: str = ""
    uploads_enabled: bool = True
    is_active: bool = True


class EventUpdateAdmin(EventDateModel):
    album_public: bool | None = None
    access_code: str | None = Field(default=None, max_length=64)

    @field_validator("access_code")
    @classmethod
    def code_length(cls, value):
        if value is not None and value != "" and (len(value) < 6 or len(value.encode("utf-8")) > 72):
            raise ValueError("Erişim kodu en az 6 karakter ve en fazla 72 bayt olmalı.")
        return value

    name: str | None = Field(default=None, min_length=1, max_length=255)
    slug: str | None = Field(default=None, max_length=64)
    event_date: datetime | None = None
    venue: str | None = None
    city: str | None = None
    is_active: bool | None = None
    uploads_enabled: bool | None = None
