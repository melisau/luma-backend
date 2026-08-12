from io import BytesIO

import qrcode
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import Response
from sqlalchemy.orm import Session

from app.api.photos import get_event_by_token
from app.core.config import get_settings
from app.db.database import get_db
from app.schemas.event import EventPublic

router = APIRouter(prefix="/events", tags=["events"])


def upload_page_url(request: Request, event_token: str) -> str:
    settings = get_settings()
    base = (settings.public_base_url or str(request.base_url)).rstrip("/")
    return f"{base}/e/{event_token}/upload"


@router.get("/{event_token}", response_model=EventPublic)
def get_event(event_token: str, db: Session = Depends(get_db)):
    event = get_event_by_token(db, event_token)
    return EventPublic.model_validate(event)


@router.get("/{event_token}/upload-qr")
def upload_qr(
    event_token: str,
    request: Request,
    size: str = "screen",
    download: bool = False,
    db: Session = Depends(get_db),
):
    event = get_event_by_token(db, event_token)
    if not event.is_active:
        raise HTTPException(status_code=404, detail="Etkinlik bulunamadı.")

    url = upload_page_url(request, event.private_token)
    box_size = 24 if size == "print" else 9
    qr = qrcode.QRCode(
        version=None,
        error_correction=qrcode.constants.ERROR_CORRECT_H,
        box_size=box_size,
        border=4,
    )
    qr.add_data(url)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")

    buffer = BytesIO()
    img.save(buffer, format="PNG")
    filename = "luma-fotograf-yukleme-qr-baski.png" if size == "print" else "luma-fotograf-yukleme-qr.png"
    disposition = "attachment" if download else "inline"
    return Response(
        content=buffer.getvalue(),
        media_type="image/png",
        headers={
            "Cache-Control": "private, no-store",
            "Content-Disposition": f'{disposition}; filename="{filename}"',
        },
    )
