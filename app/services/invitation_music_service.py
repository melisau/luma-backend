import uuid
from pathlib import Path

from fastapi import HTTPException, UploadFile, status
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.models import Event
from app.services.storage import get_storage as get_storage_backend

ALLOWED_MUSIC_MIME = {
    "audio/mpeg": ".mp3",
    "audio/mp3": ".mp3",
    "audio/mp4": ".m4a",
    "audio/x-m4a": ".m4a",
    "audio/wav": ".wav",
    "audio/x-wav": ".wav",
    "audio/ogg": ".ogg",
}
MAX_MUSIC_BYTES = 15 * 1024 * 1024


class InvitationMusicService:
    def __init__(self):
        self.storage = get_storage_backend()
        self.settings = get_settings()

    def music_url(self, event: Event, event_token: str) -> str | None:
        if not event.music_storage_key:
            return None
        return f"/api/events/{event_token}/music"

    def _resolve_mime(self, upload: UploadFile, raw: bytes) -> str:
        content_type = (upload.content_type or "").split(";", 1)[0].strip().lower()
        if content_type in ALLOWED_MUSIC_MIME:
            return content_type
        ext = Path(upload.filename or "").suffix.lower()
        fallback = {
            ".mp3": "audio/mpeg",
            ".m4a": "audio/mp4",
            ".wav": "audio/wav",
            ".ogg": "audio/ogg",
        }.get(ext)
        if fallback:
            return fallback
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Desteklenmeyen müzik formatı. MP3, M4A, WAV veya OGG yükleyin.",
        )

    def upload_music(self, db: Session, event: Event, upload: UploadFile) -> Event:
        raw = upload.file.read()
        if not raw:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Boş dosya.")
        if len(raw) > MAX_MUSIC_BYTES:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Müzik dosyası en fazla 15 MB olabilir.",
            )

        mime_type = self._resolve_mime(upload, raw)
        ext = ALLOWED_MUSIC_MIME[mime_type]

        if event.music_storage_key:
            try:
                self.storage.delete(event.music_storage_key)
            except Exception:
                pass

        key = f"events/{event.id}/music/{uuid.uuid4().hex}{ext}"
        self.storage.put_bytes(key, raw, mime_type)
        event.music_storage_key = key
        event.music_filename = (upload.filename or f"music{ext}")[:512]
        event.music_mime_type = mime_type
        db.commit()
        db.refresh(event)
        return event

    def stream_music(self, event: Event) -> tuple[bytes, str]:
        if not event.music_storage_key:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Müzik dosyası yok.")
        content_type = event.music_mime_type or "audio/mpeg"
        return self.storage.get_bytes(event.music_storage_key), content_type

    def remove_music(self, db: Session, event: Event) -> Event:
        if event.music_storage_key:
            try:
                self.storage.delete(event.music_storage_key)
            except Exception:
                pass
            event.music_storage_key = None
            event.music_filename = None
            event.music_mime_type = None
            db.commit()
            db.refresh(event)
        return event
