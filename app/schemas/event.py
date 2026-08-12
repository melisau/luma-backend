from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class EventPublic(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    name: str
    slug: str
    is_active: bool
    uploads_enabled: bool
    created_at: datetime
    event_date: datetime | None = None
    venue: str = ""
    city: str = ""


class EventAdmin(EventPublic):
    private_token: str
    invite_path: str


class EventCreateAdmin(BaseModel):
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


class EventUpdateAdmin(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    slug: str | None = Field(default=None, max_length=64)
    event_date: datetime | None = None
    venue: str | None = None
    city: str | None = None
    is_active: bool | None = None
    uploads_enabled: bool | None = None
