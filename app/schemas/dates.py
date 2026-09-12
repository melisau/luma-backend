from datetime import datetime, timezone
from pydantic import BaseModel, field_validator


class EventDateModel(BaseModel):
    # SQLite drops timezone metadata; all stored event times use UTC.
    @field_validator("event_date", check_fields=False)
    @classmethod
    def event_date_utc(cls, value: datetime | None) -> datetime | None:
        if value is None:
            return None
        return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)
