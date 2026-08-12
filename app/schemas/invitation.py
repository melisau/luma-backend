from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class InvitationPublic(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    name: str
    slug: str
    event_date: datetime | None = None
    venue: str = ""
    city: str = ""
    tagline: str = ""
    story_title: str = ""
    story_text: str = ""
    guest_note: str = ""
    cover_url: str | None = None
    music_url: str | None = None
    music_filename: str | None = None


class InvitationUpdateAdmin(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    event_date: datetime | None = None
    venue: str | None = None
    city: str | None = None
    tagline: str | None = None
    story_title: str | None = None
    story_text: str | None = None
    guest_note: str | None = None
