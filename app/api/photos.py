import logging
from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, Header, HTTPException, Request, UploadFile, status
from fastapi.responses import Response
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.security import create_admin_token, verify_password
from app.db.database import get_db
from app.db.models import AdminUser, Event
from app.schemas.event import EventAdmin, EventPublic
from app.schemas.photo import (
    AdminLoginRequest,
    AdminLoginResponse,
    PhotoAdmin,
    PhotoPublic,
    PhotoUpdateAdmin,
    PhotoUploadResponse,
    SignedPhotoResponse,
)
from app.services.photo_service import PhotoService
from app.services.rate_limit import enforce_upload_rate_limit

logger = logging.getLogger(__name__)

router = APIRouter(tags=["photos"])


def get_photo_service() -> PhotoService:
    return PhotoService()


def get_event_by_token(db: Session, event_token: str) -> Event:
    event = db.query(Event).filter(Event.private_token == event_token).one_or_none()
    if not event:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Etkinlik bulunamadı.")
    if not event.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Bu etkinlik artık aktif değil.")
    return event


def photo_public(photo, event_token: str, *, admin: bool = False) -> PhotoPublic | PhotoAdmin:
    settings = get_settings()
    base = f"/api/photos/{photo.id}"
    token_query = f"?access={event_token}" if not admin else ""
    thumb = f"{base}/thumbnail{token_query}"
    original = f"{base}{token_query}"
    if admin:
        return PhotoAdmin(
            id=photo.id,
            created_at=photo.created_at,
            original_filename=photo.original_filename,
            mime_type=photo.mime_type,
            size=photo.size,
            width=photo.width,
            height=photo.height,
            uploader_name=photo.uploader_name,
            caption=photo.caption,
            status=photo.status,
            favorite=photo.favorite,
            thumbnail_url=thumb,
            original_url=original,
        )
    return PhotoPublic(
        id=photo.id,
        created_at=photo.created_at,
        thumbnail_url=thumb,
        uploader_name=photo.uploader_name,
    )


def _resolve_admin(authorization: str | None, db: Session) -> AdminUser:
    from app.core.security import decode_admin_token

    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Yönetici oturumu gerekli.")
    token = authorization.removeprefix("Bearer ").strip()
    email = decode_admin_token(token)
    if not email:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Yönetici oturumu geçersiz.")
    admin = db.query(AdminUser).filter(AdminUser.email == email).one_or_none()
    if not admin:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Yönetici oturumu geçersiz.")
    return admin


def get_current_admin(
    authorization: Annotated[str | None, Header()] = None,
    db: Session = Depends(get_db),
) -> AdminUser:
    return _resolve_admin(authorization, db)


@router.get("/events/{event_token}/photos", response_model=list[PhotoPublic])
def list_event_photos(
    event_token: str,
    db: Session = Depends(get_db),
    photos: PhotoService = Depends(get_photo_service),
):
    event = get_event_by_token(db, event_token)
    items = photos.list_photos_for_guest(db, event)
    return [photo_public(item, event_token) for item in items]


@router.post("/events/{event_token}/photos", response_model=PhotoUploadResponse)
async def upload_event_photos(
    request: Request,
    event_token: str,
    uploader_name: Annotated[str, Form()],
    caption: Annotated[str, Form()] = "",
    files: Annotated[list[UploadFile], File()] = ...,
    db: Session = Depends(get_db),
    photos: PhotoService = Depends(get_photo_service),
):
    if not files:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="En az bir dosya gerekli.")

    client_ip = request.client.host if request.client else "unknown"
    enforce_upload_rate_limit(client_ip, event_token)

    try:
        saved = photos.upload_photos(db, event_token, files, uploader_name, caption)
    except HTTPException:
        raise
    except Exception:
        logger.exception("Photo upload failed")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Fotoğraf yüklenirken bir hata oluştu. Lütfen tekrar deneyin.",
        ) from None

    return PhotoUploadResponse(uploaded=[photo_public(item, event_token) for item in saved])



@router.get("/photos/{photo_id}")
def get_photo(
    photo_id: str,
    access: str | None = None,
    x_event_token: Annotated[str | None, Header()] = None,
    authorization: Annotated[str | None, Header()] = None,
    db: Session = Depends(get_db),
    photos: PhotoService = Depends(get_photo_service),
):
    photo = None
    if authorization and authorization.startswith("Bearer "):
        _resolve_admin(authorization, db)
        photo = photos.get_photo_admin(db, photo_id)
    else:
        token = x_event_token or access
        if not token:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Erişim reddedildi.")
        photo = photos.get_photo_for_event(db, photo_id, token)
    signed = photos.signed_access_url(photo, thumbnail=False)
    if signed:
        return SignedPhotoResponse(url=signed, expires_in=get_settings().signed_url_expiry_seconds)

    data, content_type = photos.stream_photo(photo, thumbnail=False)
    return Response(
        content=data,
        media_type=content_type,
        headers={
            "Cache-Control": "private, no-store",
            "X-Robots-Tag": "noindex, nofollow, noimageindex",
            "Referrer-Policy": "no-referrer",
            "X-Content-Type-Options": "nosniff",
        },
    )


@router.get("/photos/{photo_id}/thumbnail")
def get_photo_thumbnail(
    photo_id: str,
    access: str | None = None,
    x_event_token: Annotated[str | None, Header()] = None,
    authorization: Annotated[str | None, Header()] = None,
    db: Session = Depends(get_db),
    photos: PhotoService = Depends(get_photo_service),
):
    photo = None
    if authorization and authorization.startswith("Bearer "):
        _resolve_admin(authorization, db)
        photo = photos.get_photo_admin(db, photo_id)
    else:
        token = x_event_token or access
        if not token:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Erişim reddedildi.")
        photo = photos.get_photo_for_event(db, photo_id, token)
    signed = photos.signed_access_url(photo, thumbnail=True)
    if signed:
        return SignedPhotoResponse(url=signed, expires_in=get_settings().signed_url_expiry_seconds)

    data, content_type = photos.stream_photo(photo, thumbnail=True)
    return Response(
        content=data,
        media_type=content_type,
        headers={
            "Cache-Control": "private, no-store",
            "X-Robots-Tag": "noindex, nofollow, noimageindex",
            "Referrer-Policy": "no-referrer",
            "X-Content-Type-Options": "nosniff",
        },
    )


@router.post("/admin/login", response_model=AdminLoginResponse)
def admin_login(payload: AdminLoginRequest, db: Session = Depends(get_db)):
    admin = db.query(AdminUser).filter(AdminUser.email == payload.email.lower()).one_or_none()
    if not admin or not verify_password(payload.password, admin.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Geçersiz kimlik bilgileri.")
    return AdminLoginResponse(access_token=create_admin_token(admin.email))


@router.get("/admin/events", response_model=list[EventAdmin])
def admin_list_events(
    db: Session = Depends(get_db),
    _admin: AdminUser = Depends(get_current_admin),
):
    events = db.query(Event).order_by(Event.created_at.desc()).all()
    return [
        EventAdmin(
            name=event.name,
            slug=event.slug,
            is_active=event.is_active,
            uploads_enabled=event.uploads_enabled,
            created_at=event.created_at,
            private_token=event.private_token,
            invite_path=f"/e/{event.private_token}",
        )
        for event in events
    ]


@router.get("/admin/events/{event_token}/photos", response_model=list[PhotoAdmin])
def admin_list_photos(
    event_token: str,
    db: Session = Depends(get_db),
    _admin: AdminUser = Depends(get_current_admin),
    photos: PhotoService = Depends(get_photo_service),
):
    event = db.query(Event).filter(Event.private_token == event_token).one_or_none()
    if not event:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Etkinlik bulunamadı.")
    items = photos.list_photos_for_event_admin(db, event.id)
    return [photo_public(item, event_token, admin=True) for item in items]


@router.delete("/admin/photos/{photo_id}", status_code=status.HTTP_204_NO_CONTENT)
def admin_delete_photo(
    photo_id: str,
    db: Session = Depends(get_db),
    _admin: AdminUser = Depends(get_current_admin),
    photos: PhotoService = Depends(get_photo_service),
):
    photos.delete_photo_admin(db, photo_id)


@router.patch("/admin/photos/{photo_id}", response_model=PhotoAdmin)
def admin_update_photo(
    photo_id: str,
    payload: PhotoUpdateAdmin,
    db: Session = Depends(get_db),
    admin: AdminUser = Depends(get_current_admin),
    photos: PhotoService = Depends(get_photo_service),
):
    photo = photos.update_photo_admin(
        db,
        photo_id,
        favorite=payload.favorite,
        status_value=payload.status,
    )
    event = db.query(Event).filter(Event.id == photo.event_id).one()
    return photo_public(photo, event.private_token, admin=True)
