from io import BytesIO
import re
import uuid
from fastapi import HTTPException
from PIL import Image, ImageOps
from app.services.storage import get_storage

def asset_key(event, asset_id):
    if not re.fullmatch(r"[a-f0-9]{32}", asset_id) or asset_id not in (event.visual_assets or []):
        raise HTTPException(status_code=404, detail="Görsel bulunamadı.")
    return f"events/{event.id}/visual-assets/{asset_id}.webp"

def upload_asset(db, event, upload):
    if len(event.visual_assets or []) >= 32:
        raise HTTPException(status_code=400, detail="Bu etkinlikte en fazla 32 görsel saklanabilir.")
    raw = upload.file.read(5 * 1024 * 1024 + 1)
    if not raw or len(raw) > 5 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="Görsel en fazla 5 MB olabilir.")
    try:
        image = Image.open(BytesIO(raw))
        if image.format not in {"JPEG", "PNG", "WEBP"} or image.width * image.height > 40_000_000:
            raise ValueError("Unsupported image")
        image = ImageOps.exif_transpose(image).convert("RGBA")
        image.thumbnail((2400, 2400))
        output = BytesIO()
        image.save(output, "WEBP", quality=90)
    except Exception as exc:
        raise HTTPException(status_code=400, detail="JPG, PNG veya WebP görsel seçin.") from exc
    asset_id = uuid.uuid4().hex
    get_storage().put_bytes(f"events/{event.id}/visual-assets/{asset_id}.webp", output.getvalue(), "image/webp")
    event.visual_assets = [*(event.visual_assets or []), asset_id]
    db.commit()
    return {"id": asset_id, "src": f"/api/events/{event.private_token}/visual-assets/{asset_id}"}
