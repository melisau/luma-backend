from datetime import datetime
from typing import Literal

from pydantic import BaseModel, EmailStr

EventRole = Literal["editor", "viewer"]


class EventMemberCreate(BaseModel):
    email: EmailStr
    role: EventRole = "viewer"


class EventMemberUpdate(BaseModel):
    role: EventRole


class EventMemberPublic(BaseModel):
    id: str
    email: str
    display_name: str | None = None
    role: Literal["owner", "editor", "viewer"]
    created_at: datetime
