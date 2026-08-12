from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


GuestStatusLiteral = Literal["attending", "declined", "pending"]
GuestSourceLiteral = Literal["admin", "external"]
MessageStatusLiteral = Literal["pending", "approved", "hidden"]


class GuestPublic(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    email: str
    status: GuestStatusLiteral
    people: int
    source: GuestSourceLiteral
    created_at: datetime
    responded_at: datetime | None = None


class GuestCreateAdmin(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    email: str = Field(min_length=3, max_length=255)
    status: GuestStatusLiteral = "pending"
    people: int = Field(default=1, ge=1, le=20)
    source: GuestSourceLiteral = "admin"


class GuestUpdateAdmin(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    email: str | None = Field(default=None, min_length=3, max_length=255)
    status: GuestStatusLiteral | None = None
    people: int | None = Field(default=None, ge=1, le=20)


class RsvpSubmit(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    email: str = Field(min_length=3, max_length=255)
    status: GuestStatusLiteral
    people: int = Field(default=1, ge=1, le=20)


class GuestbookMessagePublic(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    message: str
    status: MessageStatusLiteral = "approved"
    created_at: datetime


class GuestbookMessageCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    message: str = Field(min_length=1, max_length=5000)


class GuestbookMessageUpdateAdmin(BaseModel):
    status: MessageStatusLiteral
