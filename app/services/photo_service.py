import io
import uuid
from dataclasses import dataclass
from pathlib import Path

from fastapi import HTTPException, UploadFile, status
from PIL import Image, UnidentifiedImageError
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.models import Event, Photo, PhotoStatus
from app.services.storage import StorageBackend, get_storage

try:
    import pillow_heif

    pillow_heif.register_heif_opener()
except ImportError:
    pillow_heif = None

ALLOWED_MIME = {
    "image/jpeg": ".jpg",
    "image/jpg": ".jpg",
    "image/pjpeg": ".jpg",
    "image/png": ".png",
    "image/webp": ".webp",
    "image/heic": ".heic",
    "image/heif": ".heif",
}


@dataclass
class ProcessedImage:
    original_bytes: bytes
    thumb_bytes: bytes
    mime_type: str
    width: int
    height: int
    size: int


class PhotoService:
    def __init__(self, storage: StorageBackend | None = None):
        self.storage = storage or get_storage()
        self.settings = get_settings()

    def _validate_event(self, db: Session, event_token: str) -> Event:
        event = db.query(Event).filter(Event.private_token == event_token).one_or_none()
        if not event:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Etkinlik bulunamadı.")
        if not event.is_active:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Bu etkinlik artık aktif değil.")
        if not event.uploads_enabled or not self.settings.uploads_enabled:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Fotoğraf yüklemeleri kapalı.")
        return event

    def _count_event_photos(self, db: Session, event_id: str) -> int:
        return (
            db.query(Photo)
            .filter(Photo.event_id == event_id, Photo.status != PhotoStatus.DELETED.value)
            .count()
        )

    def _sniff_mime(self, raw: bytes, filename: str | None) -> str | None:
        if raw.startswith(b"\xff\xd8\xff"):
            return "image/jpeg"
        if raw.startswith(b"\x89PNG\r\n\x1a\n"):
            return "image/png"
        if len(raw) >= 12 and raw[:4] == b"RIFF" and raw[8:12] == b"WEBP":
            return "image/webp"
        ext = Path(filename or "").suffix.lower()
        if ext in {".heic", ".heif"}:
            return "image/heic"
        if ext in {".jpg", ".jpeg"}:
            return "image/jpeg"
        if ext == ".png":
            return "image/png"
        if ext == ".webp":
            return "image/webp"
        return None

    def _resolve_content_type(self, upload: UploadFile, raw: bytes) -> str:
        content_type = (upload.content_type or "").split(";", 1)[0].strip().lower()
        if content_type in ALLOWED_MIME:
            return content_type
        sniffed = self._sniff_mime(raw, upload.filename)
        if sniffed:
            return sniffed
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Desteklenmeyen dosya türü. JPG, PNG, WebP veya HEIC yükleyin.",
        )

    def _open_image(self, raw: bytes) -> Image.Image:
        try:
            image = Image.open(io.BytesIO(raw))
            image.load()
        except UnidentifiedImageError as exc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Geçersiz görsel dosyası.",
            ) from exc

        if getattr(image, "n_frames", 1) > 1:
            image.seek(0)
        return image

    def _normalize_output(self, image: Image.Image, content_type: str) -> tuple[Image.Image, str, str]:
        detected = (image.format or "").lower()
        if detected in {"mpo", "jfif", "jpg"}:
            detected = "jpeg"
        if detected in {"heic", "heif"}:
            detected = "jpeg"
            content_type = "image/jpeg"

        if detected not in {"jpeg", "png", "webp"}:
            if content_type == "image/png":
                detected = "png"
            elif content_type == "image/webp":
                detected = "webp"
            else:
                detected = "jpeg"
                content_type = "image/jpeg"

        if image.mode not in ("RGB", "L"):
            image = image.convert("RGB")

        save_format = {"jpeg": "JPEG", "png": "PNG", "webp": "WEBP"}[detected]
        mime_type = {
            "JPEG": "image/jpeg",
            "PNG": "image/png",
            "WEBP": "image/webp",
        }[save_format]
        return image, save_format, mime_type

    def _process_image(self, upload: UploadFile, raw: bytes) -> ProcessedImage:
        if len(raw) > self.settings.max_photo_size_bytes:
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail="Fotoğraf boyutu izin verilen sınırı aşıyor.",
            )

        content_type = self._resolve_content_type(upload, raw)
        image = self._open_image(raw)
        image, save_format, mime_type = self._normalize_output(image, content_type)

        width, height = image.size
        original_buffer = io.BytesIO()
        if save_format == "JPEG":
            image.save(original_buffer, format=save_format, quality=92, optimize=True)
        elif save_format == "PNG":
            image.save(original_buffer, format=save_format, optimize=True)
        else:
            image.save(original_buffer, format=save_format, quality=90, method=6)

        original_bytes = original_buffer.getvalue()

        thumb = image.copy()
        thumb.thumbnail((400, 400), Image.Resampling.LANCZOS)
        thumb_buffer = io.BytesIO()
        thumb.save(thumb_buffer, format="JPEG", quality=85, optimize=True)
        thumb_bytes = thumb_buffer.getvalue()

        return ProcessedImage(
            original_bytes=original_bytes,
            thumb_bytes=thumb_bytes,
            mime_type=mime_type,
            width=width,
            height=height,
            size=len(original_bytes),
        )

    def upload_photos(
        self,
        db: Session,
        event_token: str,
        files: list[UploadFile],
        uploader_name: str,
        caption: str = "",
    ) -> list[Photo]:
        event = self._validate_event(db, event_token)
        current_count = self._count_event_photos(db, event.id)
        if current_count + len(files) > self.settings.max_photos_per_event:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Bu etkinlik için fotoğraf limiti doldu.",
            )

        saved: list[Photo] = []
        for upload in files:
            raw = upload.file.read()
            processed = self._process_image(upload, raw)
            photo_id = str(uuid.uuid4())
            ext = ALLOWED_MIME.get(processed.mime_type, ".jpg")
            original_key = f"events/{event.id}/photos/original/{photo_id}{ext}"
            thumb_key = f"events/{event.id}/photos/thumb/{photo_id}.jpg"

            self.storage.put_bytes(original_key, processed.original_bytes, processed.mime_type)
            self.storage.put_bytes(thumb_key, processed.thumb_bytes, "image/jpeg")

            photo = Photo(
                id=photo_id,
                event_id=event.id,
                storage_key_original=original_key,
                storage_key_thumb=thumb_key,
                original_filename=upload.filename,
                mime_type=processed.mime_type,
                size=processed.size,
                width=processed.width,
                height=processed.height,
                uploader_name=uploader_name.strip()[:255],
                caption=caption.strip(),
                status=PhotoStatus.UPLOADED.value,
            )
            db.add(photo)
            saved.append(photo)

        db.commit()
        for photo in saved:
            db.refresh(photo)
        if saved:
            from app.services.activity_service import record_activity

            count = len(saved)
            name = uploader_name.strip()[:255]
            record_activity(
                db,
                event,
                f"{name}, {count} yeni fotoğraf yükledi",
                "image",
            )
        return saved

    def get_event_for_upload(self, db: Session, event_token: str) -> Event:
        return self._validate_event(db, event_token)

    def list_photos_for_guest(self, db: Session, event: Event) -> list[Photo]:
        return (
            db.query(Photo)
            .filter(
                Photo.event_id == event.id,
                Photo.status == PhotoStatus.APPROVED.value,
            )
            .order_by(Photo.created_at.desc())
            .all()
        )

    def list_photos_for_event_admin(self, db: Session, event_id: str) -> list[Photo]:
        return (
            db.query(Photo)
            .filter(Photo.event_id == event_id, Photo.status != PhotoStatus.DELETED.value)
            .order_by(Photo.created_at.desc())
            .all()
        )

    def get_photo_for_event(self, db: Session, photo_id: str, event_token: str) -> Photo:
        event = db.query(Event).filter(Event.private_token == event_token).one_or_none()
        if not event or not event.is_active:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Fotoğraf bulunamadı.")

        photo = (
            db.query(Photo)
            .filter(
                Photo.id == photo_id,
                Photo.event_id == event.id,
                Photo.status == PhotoStatus.APPROVED.value,
            )
            .one_or_none()
        )
        if not photo:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Fotoğraf bulunamadı.")
        return photo

    def get_photo_admin(self, db: Session, photo_id: str, admin_id: str | None = None) -> Photo:
        query = db.query(Photo).filter(Photo.id == photo_id, Photo.status != PhotoStatus.DELETED.value)
        if admin_id is not None:
            query = query.join(Event).filter(Event.admin_id == admin_id)
        photo = query.one_or_none()
        if not photo:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Fotoğraf bulunamadı.")
        return photo

    def stream_photo(self, photo: Photo, *, thumbnail: bool = False) -> tuple[bytes, str]:
        key = photo.storage_key_thumb if thumbnail else photo.storage_key_original
        if not key:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Fotoğraf bulunamadı.")
        data = self.storage.get_bytes(key)
        content_type = "image/jpeg" if thumbnail else photo.mime_type
        return data, content_type

    def signed_access_url(self, photo: Photo, *, thumbnail: bool = False) -> str | None:
        key = photo.storage_key_thumb if thumbnail else photo.storage_key_original
        if not key:
            return None
        return self.storage.create_signed_url(key, self.settings.signed_url_expiry_seconds)

    def delete_photo_admin(self, db: Session, photo_id: str, admin_id: str) -> None:
        photo = self.get_photo_admin(db, photo_id, admin_id)
        try:
            self.storage.delete(photo.storage_key_original)
            if photo.storage_key_thumb:
                self.storage.delete(photo.storage_key_thumb)
        except Exception:
            pass
        photo.status = PhotoStatus.DELETED.value
        db.commit()

    def update_photo_admin(
        self,
        db: Session,
        photo_id: str,
        *,
        admin_id: str,
        favorite: bool | None,
        status_value: str | None,
    ) -> Photo:
        photo = self.get_photo_admin(db, photo_id, admin_id)
        if favorite is not None:
            photo.favorite = favorite
        if status_value is not None:
            allowed = {
                PhotoStatus.UPLOADED.value,
                PhotoStatus.APPROVED.value,
                PhotoStatus.HIDDEN.value,
            }
            if status_value not in allowed:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Geçersiz durum. uploaded, approved veya hidden kullanın.",
                )
            photo.status = status_value
        db.commit()
        db.refresh(photo)
        return photo
