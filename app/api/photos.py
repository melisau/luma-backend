import logging
from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, Header, HTTPException, Request, UploadFile, status
from fastapi.responses import Response
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.security import create_admin_token, hash_password, verify_password
from app.db.database import get_db
from app.db.models import AdminUser, Event, EventMember
from app.schemas.admin import AdminProfile, AdminProfileUpdate
from app.schemas.event import EventAdmin, EventCreateAdmin, EventUpdateAdmin
from app.schemas.photo import (
    AdminChangePasswordRequest,
    AdminLoginRequest,
    AdminLoginResponse,
    AdminRegisterRequest,
    PhotoAdmin,
    PhotoPublic,
    PhotoUpdateAdmin,
    PhotoUploadResponse,
    SignedPhotoResponse,
)
from app.services.event_service import (
    create_event_admin,
    delete_event_admin,
    event_to_admin,
    get_admin_event_or_404,
    update_event_admin,
)
from app.services.photo_service import PhotoService
from app.services.rate_limit import enforce_login_rate_limit, enforce_upload_rate_limit

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

    return PhotoUploadResponse(uploaded=[photo_public(item, event_token) for item in saved], duplicates_skipped=len(files)-len(saved))



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
        admin = _resolve_admin(authorization, db)
        photo = photos.get_photo_admin(db, photo_id, admin.id, write=False)
    else:
        token = x_event_token or access
        if not token:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Erişim reddedildi.")
        photo = photos.get_photo_for_event(db, photo_id, token)
    signed = photos.signed_access_url(photo, thumbnail=False) if authorization and authorization.startswith("Bearer ") else None
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
        admin = _resolve_admin(authorization, db)
        photo = photos.get_photo_admin(db, photo_id, admin.id, write=False)
    else:
        token = x_event_token or access
        if not token:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Erişim reddedildi.")
        photo = photos.get_photo_for_event(db, photo_id, token)
    signed = photos.signed_access_url(photo, thumbnail=True) if authorization and authorization.startswith("Bearer ") else None
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


@router.post("/admin/register", response_model=AdminLoginResponse, status_code=status.HTTP_201_CREATED)
def admin_register(payload: AdminRegisterRequest, request: Request, db: Session = Depends(get_db)):
    client_ip = request.client.host if request.client else "unknown"
    enforce_login_rate_limit(client_ip)
    email = payload.email.strip().lower()
    if not email:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Geçerli bir e-posta adresi girin.")
    if db.query(AdminUser).filter(AdminUser.email == email).one_or_none():
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Bu e-posta adresi zaten kayıtlı.")
    display_name = payload.display_name.strip() if payload.display_name and payload.display_name.strip() else None
    admin = AdminUser(
        email=email,
        password_hash=hash_password(payload.password),
        display_name=display_name,
    )
    db.add(admin)
    db.commit()
    db.refresh(admin)
    return AdminLoginResponse(
        access_token=create_admin_token(admin.email),
        email=admin.email,
        display_name=admin.display_name,
    )


@router.post("/admin/login", response_model=AdminLoginResponse)
def admin_login(payload: AdminLoginRequest, request: Request, db: Session = Depends(get_db)):
    client_ip = request.client.host if request.client else "unknown"
    enforce_login_rate_limit(client_ip)
    admin = db.query(AdminUser).filter(AdminUser.email == payload.email.lower()).one_or_none()
    if not admin or not verify_password(payload.password, admin.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Geçersiz kimlik bilgileri.")
    return AdminLoginResponse(
        access_token=create_admin_token(admin.email),
        email=admin.email,
        display_name=admin.display_name,
    )


@router.get("/admin/me", response_model=AdminProfile)
def admin_me(admin: AdminUser = Depends(get_current_admin)):
    return AdminProfile.model_validate(admin)


@router.patch("/admin/me", response_model=AdminProfile)
def admin_update_me(
    payload: AdminProfileUpdate,
    db: Session = Depends(get_db),
    admin: AdminUser = Depends(get_current_admin),
):
    if "display_name" in payload.model_dump(exclude_unset=True):
        name = payload.display_name
        admin.display_name = name.strip() if name and name.strip() else None
    db.commit()
    db.refresh(admin)
    return AdminProfile.model_validate(admin)


@router.post("/admin/change-password", status_code=status.HTTP_204_NO_CONTENT)
def admin_change_password(
    payload: AdminChangePasswordRequest,
    db: Session = Depends(get_db),
    admin: AdminUser = Depends(get_current_admin),
):
    if not verify_password(payload.current_password, admin.password_hash):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Mevcut şifre hatalı.")
    if payload.current_password == payload.new_password:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Yeni şifre mevcut şifreden farklı olmalı.",
        )
    admin.password_hash = hash_password(payload.new_password)
    db.commit()


@router.get("/admin/events", response_model=list[EventAdmin])
def admin_list_events(
    db: Session = Depends(get_db),
    admin: AdminUser = Depends(get_current_admin),
):
    owned = (
        db.query(Event)
        .filter(Event.admin_id == admin.id)
        .all()
    )
    memberships = db.query(EventMember).filter(EventMember.admin_id == admin.id).all()
    result = [event_to_admin(event, "owner") for event in owned]
    result.extend(event_to_admin(member.event, member.role) for member in memberships)
    return sorted(result, key=lambda item: item.created_at, reverse=True)


@router.post("/admin/events", response_model=EventAdmin, status_code=status.HTTP_201_CREATED)
def admin_create_event(
    payload: EventCreateAdmin,
    db: Session = Depends(get_db),
    admin: AdminUser = Depends(get_current_admin),
):
    event = create_event_admin(db, payload, admin.id)
    return event_to_admin(event)


@router.patch("/admin/events/{event_token}", response_model=EventAdmin)
def admin_update_event(
    event_token: str,
    payload: EventUpdateAdmin,
    db: Session = Depends(get_db),
    admin: AdminUser = Depends(get_current_admin),
):
    event = get_admin_event_or_404(db, event_token, admin.id, write=False)
    event = update_event_admin(db, event, payload)
    return event_to_admin(event)


@router.delete("/admin/events/{event_token}", status_code=status.HTTP_204_NO_CONTENT)
def admin_delete_event(
    event_token: str,
    db: Session = Depends(get_db),
    admin: AdminUser = Depends(get_current_admin),
):
    event = get_admin_event_or_404(db, event_token, admin.id, owner=True)
    delete_event_admin(db, event)


@router.get("/admin/events/{event_token}/photos", response_model=list[PhotoAdmin])
def admin_list_photos(
    event_token: str,
    db: Session = Depends(get_db),
    admin: AdminUser = Depends(get_current_admin),
    photos: PhotoService = Depends(get_photo_service),
):
    event = get_admin_event_or_404(db, event_token, admin.id, write=False)
    items = photos.list_photos_for_event_admin(db, event.id)
    return [photo_public(item, event_token, admin=True) for item in items]


@router.delete("/admin/photos/{photo_id}", status_code=status.HTTP_204_NO_CONTENT)
def admin_delete_photo(
    photo_id: str,
    db: Session = Depends(get_db),
    admin: AdminUser = Depends(get_current_admin),
    photos: PhotoService = Depends(get_photo_service),
):
    photos.delete_photo_admin(db, photo_id, admin.id)


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
        admin_id=admin.id,
        favorite=payload.favorite,
        status_value=payload.status,
    )
    event = db.query(Event).filter(Event.id == photo.event_id).one()
    return photo_public(photo, event.private_token, admin=True)


@router.get("/admin/events/{event_token}/album.zip")
def download_album(event_token: str, db: Session = Depends(get_db), admin: AdminUser = Depends(get_current_admin), photos: PhotoService = Depends(get_photo_service)):
    import tempfile
    import zipfile
    from fastapi.responses import StreamingResponse
    from starlette.background import BackgroundTask
    event = get_admin_event_or_404(db, event_token, admin.id)
    items = photos.list_photos_for_event_admin(db, event.id)
    if not items:
        raise HTTPException(status_code=404, detail="İndirilecek fotoğraf yok.")
    limit = 200 * 1024 * 1024
    if sum(photo.size for photo in items) > limit:
        raise HTTPException(status_code=413, detail="Albüm 200 MB sınırını aşıyor. Fotoğrafları tek tek indirin.")
    archive = tempfile.SpooledTemporaryFile(max_size=8 * 1024 * 1024, mode='w+b')
    try:
        total = 0
        with zipfile.ZipFile(archive, 'w', compression=zipfile.ZIP_STORED) as bundle:
            for photo in items:
                data, mime = photos.stream_photo(photo)
                total += len(data)
                if total > limit:
                    raise HTTPException(status_code=413, detail="Albüm 200 MB sınırını aşıyor.")
                extension = {'image/jpeg':'.jpg','image/png':'.png','image/webp':'.webp'}.get(mime,'.bin')
                bundle.writestr(f'{photo.id}{extension}', data)
        archive.seek(0)
    except HTTPException:
        archive.close()
        raise
    except Exception:
        archive.close()
        logger.exception('Album export failed')
        raise HTTPException(status_code=503, detail="Albümün bazı dosyalarına erişilemiyor. Lütfen tekrar deneyin.") from None
    def chunks():
        try:
            while chunk := archive.read(64 * 1024):
                yield chunk
        finally:
            archive.close()
    return StreamingResponse(chunks(), media_type='application/zip', headers={'Content-Disposition':'attachment; filename="luma-album.zip"','Cache-Control':'private, no-store'}, background=BackgroundTask(archive.close))
