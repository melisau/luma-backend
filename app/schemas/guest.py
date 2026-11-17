from datetime import datetime
from typing import Literal

import re

from pydantic import BaseModel, ConfigDict, Field, EmailStr, field_validator


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
    dietary_consent_at: datetime | None = None
    notes: str = ""
    group_name: str = ""
    table_name: str = ""
    created_at: datetime
    responded_at: datetime | None = None
    # Personal-link mode: how many devices opened this guest's invitation.
    device_count: int = 0
    phone: str = ""
    invite_sent_at: datetime | None = None
    opened_at: datetime | None = None


def normalize_phone(value: str | None) -> str | None:
    """'0532 123 45 67', '532 123 4567', '+90 532...' -> '+905321234567'. Empty stays empty."""
    if value is None:
        return None
    raw = value.strip()
    if not raw:
        return ""
    digits = re.sub(r"\D", "", raw)
    if raw.startswith("+"):
        pass
    elif digits.startswith("00"):
        digits = digits[2:]
    elif digits.startswith("0") and len(digits) == 11:
        digits = "90" + digits[1:]
    elif len(digits) == 10 and digits.startswith("5"):
        digits = "90" + digits
    if not 8 <= len(digits) <= 15:
        raise ValueError("Telefon numarasını ülke koduyla ya da 0 ile başlayarak yazın. Örn. 0532 123 45 67")
    return "+" + digits


class GuestInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    @field_validator("phone", mode="before", check_fields=False)
    @classmethod
    def phone_format(cls, value):
        return normalize_phone(value)


class GuestCreateAdmin(GuestInput):
    name: str = Field(min_length=1, max_length=255)
    email: EmailStr = Field(max_length=255)
    status: GuestStatusLiteral = "pending"
    people: int = Field(default=1, ge=1, le=20)
    dietary_requirements: str = Field(default="", max_length=1000)
    notes: str = Field(default="", max_length=2000)
    group_name: str = Field(default="", max_length=255)
    table_name: str = Field(default="", max_length=255)
    phone: str = Field(default="", max_length=32)
    source: GuestSourceLiteral = "admin"


class GuestUpdateAdmin(GuestInput):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    email: EmailStr | None = Field(default=None, max_length=255)
    status: GuestStatusLiteral | None = None
    people: int | None = Field(default=None, ge=1, le=20)
    dietary_requirements: str | None = Field(default=None, max_length=1000)
    notes: str | None = Field(default=None, max_length=2000)
    group_name: str | None = Field(default=None, max_length=255)
    table_name: str | None = Field(default=None, max_length=255)
    phone: str | None = Field(default=None, max_length=32)


class RsvpReceipt(GuestPublic):
    edit_token: str
    # True when the guest wrote dietary info but did not tick the consent box, so it was not stored.
    dietary_dropped: bool = False


class RsvpSubmit(GuestInput):
    edit_token: str | None = Field(default=None, min_length=32, max_length=128)
    name: str = Field(min_length=1, max_length=255)
    email: EmailStr = Field(max_length=255)
    status: GuestStatusLiteral
    people: int = Field(default=1, ge=1, le=20)
    dietary_requirements: str = Field(default="", max_length=1000)
    dietary_consent: bool = False
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
