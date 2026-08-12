import uuid
from io import BytesIO

from fastapi import HTTPException, UploadFile, status
from PIL import Image
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.models import Event
from app.services.storage import get_storage as get_storage_backend


class InvitationCoverService:
    def __init__(self):
        self.storage = get_storage_backend()
        self.settings = get_settings()

    def cover_url(self, event: Event, event_token: str) -> str | None:
        if not event.cover_storage_key:
            return None
        return f"/api/events/{event_token}/cover"

    def upload_cover(self, db: Session, event: Event, upload: UploadFile) -> Event:
        raw = upload.file.read()
        if not raw:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Boş dosya.")
        if len(raw) > 3 * 1024 * 1024:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Kapak görseli en fazla 3 MB olabilir.")

        try:
            image = Image.open(BytesIO(raw))
            image.load()
            if image.mode not in ("RGB", "RGBA"):
                image = image.convert("RGB")
            elif image.mode == "RGBA":
                background = Image.new("RGB", image.size, (255, 255, 255))
                background.paste(image, mask=image.split()[3])
                image = background
            buffer = BytesIO()
            image.save(buffer, format="JPEG", quality=88, optimize=True)
            processed = buffer.getvalue()
        except Exception as exc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Desteklenmeyen görsel formatı.",
            ) from exc

        if event.cover_storage_key:
            try:
                self.storage.delete(event.cover_storage_key)
            except Exception:
                pass

        key = f"events/{event.id}/cover/{uuid.uuid4().hex}.jpg"
        self.storage.put_bytes(key, processed, "image/jpeg")
        event.cover_storage_key = key
        db.commit()
        db.refresh(event)
        return event

    def stream_cover(self, event: Event) -> tuple[bytes, str]:
        if not event.cover_storage_key:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Kapak görseli yok.")
        return self.storage.get_bytes(event.cover_storage_key), "image/jpeg"

    def remove_cover(self, db: Session, event: Event) -> Event:
        if event.cover_storage_key:
            try:
                self.storage.delete(event.cover_storage_key)
            except Exception:
                pass
            event.cover_storage_key = None
            db.commit()
            db.refresh(event)
        return event
