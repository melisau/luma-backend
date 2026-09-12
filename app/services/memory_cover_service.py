import uuid
from io import BytesIO

from fastapi import HTTPException, UploadFile, status
from PIL import Image, ImageOps
from sqlalchemy.orm import Session

from app.db.models import Event
from app.services.storage import get_storage


class MemoryCoverService:
    def __init__(self):
        self.storage = get_storage()

    def url(self, event: Event, token: str) -> str | None:
        return f"/api/events/{token}/memory-cover" if event.memory_cover_storage_key else None

    def upload(self, db: Session, event: Event, upload: UploadFile) -> Event:
        raw = upload.file.read()
        if not raw or len(raw) > 3 * 1024 * 1024:
            raise HTTPException(status_code=400, detail="Anı görseli boş olamaz ve en fazla 3 MB olabilir.")
        try:
            image = ImageOps.exif_transpose(Image.open(BytesIO(raw))).convert("RGB")
            image.thumbnail((2400, 2400))
            buffer = BytesIO()
            image.save(buffer, "JPEG", quality=88, optimize=True)
        except Exception as exc:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Desteklenmeyen görsel formatı.") from exc
        old = event.memory_cover_storage_key
        key = f"events/{event.id}/memory-cover/{uuid.uuid4().hex}.jpg"
        self.storage.put_bytes(key, buffer.getvalue(), "image/jpeg")
        event.memory_cover_storage_key = key
        db.commit(); db.refresh(event)
        if old:
            try: self.storage.delete(old)
            except Exception: pass
        return event

    def stream(self, event: Event) -> tuple[bytes, str]:
        if not event.memory_cover_storage_key:
            raise HTTPException(status_code=404, detail="Anı bölümü görseli yok.")
        return self.storage.get_bytes(event.memory_cover_storage_key), "image/jpeg"

    def remove(self, db: Session, event: Event) -> Event:
        key = event.memory_cover_storage_key
        if key:
            event.memory_cover_storage_key = None
            db.commit(); db.refresh(event)
            try: self.storage.delete(key)
            except Exception: pass
        return event
