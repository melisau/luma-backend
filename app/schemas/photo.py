from datetime import datetime

from pydantic import BaseModel, ConfigDict


class EventPublic(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    name: str
    slug: str
    is_active: bool
    uploads_enabled: bool
    created_at: datetime


class PhotoPublic(BaseModel):
    id: str
    created_at: datetime
    thumbnail_url: str
    uploader_name: str


class PhotoAdmin(BaseModel):
    id: str
    created_at: datetime
    original_filename: str | None
    mime_type: str
    size: int
    width: int
    height: int
    uploader_name: str
    caption: str
    status: str
    favorite: bool
    thumbnail_url: str
    original_url: str


class PhotoUploadResponse(BaseModel):
    uploaded: list[PhotoPublic]


class PhotoUpdateAdmin(BaseModel):
    favorite: bool | None = None
    status: str | None = None


class AdminLoginRequest(BaseModel):
    email: str
    password: str


class AdminLoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class SignedPhotoResponse(BaseModel):
    url: str
    expires_in: int
