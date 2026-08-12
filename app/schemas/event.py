from datetime import datetime

from pydantic import BaseModel, ConfigDict


class EventPublic(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    name: str
    slug: str
    is_active: bool
    uploads_enabled: bool
    created_at: datetime


class EventAdmin(EventPublic):
    private_token: str
    invite_path: str
