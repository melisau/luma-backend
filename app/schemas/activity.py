from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class ActivityPublic(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    text: str
    kind: str
    created_at: datetime


class ActivityCreate(BaseModel):
    text: str = Field(min_length=1, max_length=512)
    kind: str = Field(default="check", min_length=1, max_length=32)
