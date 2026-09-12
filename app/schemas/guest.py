from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, EmailStr


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
    dietary_requirements: str = ""
    notes: str = ""
    created_at: datetime
    responded_at: datetime | None = None


class GuestInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)


class GuestCreateAdmin(GuestInput):
    name: str = Field(min_length=1, max_length=255)
    email: EmailStr = Field(max_length=255)
    status: GuestStatusLiteral = "pending"
    people: int = Field(default=1, ge=1, le=20)
    dietary_requirements: str = Field(default="", max_length=1000)
    notes: str = Field(default="", max_length=2000)
    source: GuestSourceLiteral = "admin"


class GuestUpdateAdmin(GuestInput):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    email: EmailStr | None = Field(default=None, max_length=255)
    status: GuestStatusLiteral | None = None
    people: int | None = Field(default=None, ge=1, le=20)
    dietary_requirements: str | None = Field(default=None, max_length=1000)
    notes: str | None = Field(default=None, max_length=2000)


class RsvpReceipt(GuestPublic):
    edit_token: str


class RsvpSubmit(GuestInput):
    edit_token: str | None = Field(default=None, min_length=32, max_length=128)
    name: str = Field(min_length=1, max_length=255)
    email: EmailStr = Field(max_length=255)
    status: GuestStatusLiteral
    people: int = Field(default=1, ge=1, le=20)
    dietary_requirements: str = Field(default="", max_length=1000)
    notes: str = Field(default="", max_length=2000)


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
