from typing import Annotated

from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile, status
from fastapi.responses import Response, JSONResponse
from sqlalchemy.orm import Session
from pydantic import BaseModel, Field
from typing import Literal

from app.api.photos import get_current_admin, get_event_by_token
from app.services.event_service import get_admin_event_or_404
from app.db.database import get_db
from app.db.models import AdminUser
from app.schemas.activity import ActivityCreate, ActivityPublic
from app.schemas.contact import ContactCreate, ContactPublic
from app.schemas.guest import (
    GuestCreateAdmin,
    GuestPublic,
    GuestUpdateAdmin,
    GuestbookMessageCreate,
    GuestbookMessagePublic,
    GuestbookMessageUpdateAdmin,
    RsvpSubmit,
    RsvpReceipt,
)
from app.schemas.invitation import InvitationPublic, InvitationUpdateAdmin
from app.schemas.member import EventMemberCreate, EventMemberPublic, EventMemberUpdate
from app.services.activity_service import list_activities, record_activity
from app.services.event_data_service import (
    create_contact,
    create_guest_admin,
    create_message,
    delete_contact,
    delete_guest_admin,
    delete_message_admin,
    invitation_to_public,
    list_contacts,
    list_guests,
    list_messages,
    submit_rsvp,
    update_guest_admin,
    update_invitation_admin,
    update_message_admin,
)
from app.services.rate_limit import enforce_message_rate_limit, enforce_rsvp_rate_limit
from app.services.invitation_cover_service import InvitationCoverService
from app.services.invitation_music_service import InvitationMusicService
from app.services.memory_cover_service import MemoryCoverService
from app.services.email_service import send_email
from app.core.config import get_settings

router = APIRouter(tags=["event-data"])

@router.post("/admin/events/{event_token}/invitation/visual-assets")
def upload_visual_asset(event_token: str, file: Annotated[UploadFile, File()], db: Session = Depends(get_db), admin: AdminUser = Depends(get_current_admin)):
    from app.services.visual_asset_service import upload_asset
    event = get_admin_event_or_404(db, event_token, admin.id)
    return upload_asset(db, event, file)

@router.get("/events/{event_token}/visual-assets/{asset_id}")
def get_visual_asset(event_token: str, asset_id: str, db: Session = Depends(get_db)):
    from app.services.visual_asset_service import asset_key
    from app.services.storage import get_storage
    event = get_event_by_token(db, event_token)
    try:
        data = get_storage().get_bytes(asset_key(event, asset_id))
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Görsel bulunamadı.")
    return Response(data, media_type="image/webp", headers={"Cache-Control": "private, max-age=3600"})


def get_cover_service() -> InvitationCoverService:
    return InvitationCoverService()


def get_music_service() -> InvitationMusicService:
    return InvitationMusicService()

def get_memory_cover_service() -> MemoryCoverService:
    return MemoryCoverService()


def _cover_url(event, token: str, covers: InvitationCoverService) -> str | None:
    if not event.cover_storage_key:
        return None
    return covers.cover_url(event, token)


def _music_url(event, token: str, music: InvitationMusicService) -> str | None:
    if not event.music_storage_key:
        return None
    return music.music_url(event, token)


def _invitation_public(event, token: str, covers: InvitationCoverService, music: InvitationMusicService, memory: MemoryCoverService):
    return invitation_to_public(
        event,
        _cover_url(event, token, covers),
        _music_url(event, token, music),
        memory.url(event, token),
    )


@router.get("/events/{event_token}/invitation", response_model=InvitationPublic)
def get_public_invitation(
    event_token: str,
    db: Session = Depends(get_db),
    covers: InvitationCoverService = Depends(get_cover_service),
    music: InvitationMusicService = Depends(get_music_service),
    memory: MemoryCoverService = Depends(get_memory_cover_service),
):
    event = get_event_by_token(db, event_token)
    return _invitation_public(event, event_token, covers, music, memory)

@router.get("/events/{event_token}/memory-cover")
def get_public_memory_cover(event_token: str, db: Session = Depends(get_db), memory: MemoryCoverService = Depends(get_memory_cover_service)):
    event = get_event_by_token(db, event_token)
    data, content_type = memory.stream(event)
    return Response(content=data, media_type=content_type, headers={"Cache-Control": "private, no-store"})


@router.get("/events/{event_token}/cover")
def get_public_cover(
    event_token: str,
    db: Session = Depends(get_db),
    covers: InvitationCoverService = Depends(get_cover_service),
):
    event = get_event_by_token(db, event_token)
    data, content_type = covers.stream_cover(event)
    return Response(
        content=data,
        media_type=content_type,
        headers={"Cache-Control": "private, no-store"},
    )


@router.get("/events/{event_token}/music")
def get_public_music(
    event_token: str,
    db: Session = Depends(get_db),
    music: InvitationMusicService = Depends(get_music_service),
):
    event = get_event_by_token(db, event_token)
    data, content_type = music.stream_music(event)
    return Response(
        content=data,
        media_type=content_type,
        headers={"Cache-Control": "private, no-store"},
    )


@router.post("/events/{event_token}/rsvp", response_model=RsvpReceipt)
def public_rsvp(
    event_token: str,
    payload: RsvpSubmit,
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
):
    event = get_event_by_token(db, event_token)
    enforce_rsvp_rate_limit(request.client.host if request.client else "unknown", event_token)
    response.headers["Cache-Control"] = "no-store"
    link_guest = None
    guest_id = getattr(request.state, "luma_guest_id", None)
    if guest_id:
        from app.db.models import Guest
        link_guest = db.query(Guest).filter(Guest.id == guest_id, Guest.event_id == event.id).one_or_none()
    guest, edit_token, dietary_dropped = submit_rsvp(db, event, payload, link_guest)
    try:
        url=f"{(get_settings().public_base_url or 'http://localhost:5500').rstrip('/')}/e/{event_token}"
        send_email(guest.email,f"{event.name} RSVP onayı",f"Yanıtınız alındı: {guest.people} kişi, durum: {guest.status}. Davetiye: {url}")
    except Exception:
        import logging; logging.getLogger(__name__).exception("RSVP confirmation email failed")
    return RsvpReceipt(**GuestPublic.model_validate(guest).model_dump(), edit_token=edit_token,
                       dietary_dropped=dietary_dropped)


@router.get("/events/{event_token}/messages", response_model=list[GuestbookMessagePublic])
def list_public_messages(event_token: str, db: Session = Depends(get_db)):
    event = get_event_by_token(db, event_token)
    return [
        GuestbookMessagePublic.model_validate(item)
        for item in list_messages(db, event, approved_only=True)
    ]


@router.post("/events/{event_token}/messages", response_model=GuestbookMessagePublic)
def create_public_message(
    event_token: str,
    payload: GuestbookMessageCreate,
    request: Request,
    db: Session = Depends(get_db),
):
    client_ip = request.client.host if request.client else "unknown"
    enforce_message_rate_limit(client_ip, event_token)
    event = get_event_by_token(db, event_token)
    item = create_message(db, event, payload.name, payload.message)
    return GuestbookMessagePublic.model_validate(item)


@router.get("/admin/events/{event_token}/guests", response_model=list[GuestPublic])
def admin_list_guests(
    event_token: str,
    db: Session = Depends(get_db),
    admin: AdminUser = Depends(get_current_admin),
):
    event = get_admin_event_or_404(db, event_token, admin.id, write=False)
    return [GuestPublic.model_validate(item) for item in list_guests(db, event)]


@router.post("/admin/events/{event_token}/guests", response_model=GuestPublic, status_code=status.HTTP_201_CREATED)
def admin_create_guest(
    event_token: str,
    payload: GuestCreateAdmin,
    db: Session = Depends(get_db),
    admin: AdminUser = Depends(get_current_admin),
):
    event = get_admin_event_or_404(db, event_token, admin.id)
    guest = create_guest_admin(db, event, payload)
    return GuestPublic.model_validate(guest)


@router.patch("/admin/events/{event_token}/guests/{guest_id}", response_model=GuestPublic)
def admin_update_guest(
    event_token: str,
    guest_id: str,
    payload: GuestUpdateAdmin,
    db: Session = Depends(get_db),
    admin: AdminUser = Depends(get_current_admin),
):
    event = get_admin_event_or_404(db, event_token, admin.id)
    guest = update_guest_admin(db, event, guest_id, payload)
    return GuestPublic.model_validate(guest)


@router.delete("/admin/events/{event_token}/guests/{guest_id}", status_code=status.HTTP_204_NO_CONTENT)
def admin_delete_guest(
    event_token: str,
    guest_id: str,
    db: Session = Depends(get_db),
    admin: AdminUser = Depends(get_current_admin),
):
    event = get_admin_event_or_404(db, event_token, admin.id)
    delete_guest_admin(db, event, guest_id)


@router.get("/admin/events/{event_token}/messages", response_model=list[GuestbookMessagePublic])
def admin_list_messages(
    event_token: str,
    db: Session = Depends(get_db),
    admin: AdminUser = Depends(get_current_admin),
):
    event = get_admin_event_or_404(db, event_token, admin.id, write=False)
    return [GuestbookMessagePublic.model_validate(item) for item in list_messages(db, event)]


@router.patch("/admin/events/{event_token}/messages/{message_id}", response_model=GuestbookMessagePublic)
def admin_update_message(
    event_token: str,
    message_id: str,
    payload: GuestbookMessageUpdateAdmin,
    db: Session = Depends(get_db),
    admin: AdminUser = Depends(get_current_admin),
):
    event = get_admin_event_or_404(db, event_token, admin.id)
    item = update_message_admin(db, event, message_id, payload.status)
    return GuestbookMessagePublic.model_validate(item)


@router.delete("/admin/events/{event_token}/messages/{message_id}", status_code=status.HTTP_204_NO_CONTENT)
def admin_delete_message(
    event_token: str,
    message_id: str,
    db: Session = Depends(get_db),
    admin: AdminUser = Depends(get_current_admin),
):
    event = get_admin_event_or_404(db, event_token, admin.id)
    delete_message_admin(db, event, message_id)


@router.get("/admin/events/{event_token}/activities", response_model=list[ActivityPublic])
def admin_list_activities(
    event_token: str,
    db: Session = Depends(get_db),
    admin: AdminUser = Depends(get_current_admin),
):
    event = get_admin_event_or_404(db, event_token, admin.id, write=False)
    return [ActivityPublic.model_validate(item) for item in list_activities(db, event)]


@router.post(
    "/admin/events/{event_token}/activities",
    response_model=ActivityPublic,
    status_code=status.HTTP_201_CREATED,
)
def admin_create_activity(
    event_token: str,
    payload: ActivityCreate,
    db: Session = Depends(get_db),
    admin: AdminUser = Depends(get_current_admin),
):
    event = get_admin_event_or_404(db, event_token, admin.id)
    item = record_activity(db, event, payload.text, payload.kind)
    return ActivityPublic.model_validate(item)


@router.get("/admin/events/{event_token}/invitation", response_model=InvitationPublic)
def admin_get_invitation(
    event_token: str,
    db: Session = Depends(get_db),
    admin: AdminUser = Depends(get_current_admin),
    covers: InvitationCoverService = Depends(get_cover_service),
    music: InvitationMusicService = Depends(get_music_service),
    memory: MemoryCoverService = Depends(get_memory_cover_service),
):
    event = get_admin_event_or_404(db, event_token, admin.id, write=False)
    return _invitation_public(event, event_token, covers, music, memory)


@router.patch("/admin/events/{event_token}/invitation", response_model=InvitationPublic)
def admin_update_invitation(
    event_token: str,
    payload: InvitationUpdateAdmin,
    db: Session = Depends(get_db),
    admin: AdminUser = Depends(get_current_admin),
    covers: InvitationCoverService = Depends(get_cover_service),
    music: InvitationMusicService = Depends(get_music_service),
    memory: MemoryCoverService = Depends(get_memory_cover_service),
):
    event = get_admin_event_or_404(db, event_token, admin.id)
    event = update_invitation_admin(db, event, payload)
    return _invitation_public(event, event_token, covers, music, memory)


@router.post("/admin/events/{event_token}/invitation/cover", response_model=InvitationPublic)
def admin_upload_cover(
    event_token: str,
    file: Annotated[UploadFile, File()],
    db: Session = Depends(get_db),
    admin: AdminUser = Depends(get_current_admin),
    covers: InvitationCoverService = Depends(get_cover_service),
    music: InvitationMusicService = Depends(get_music_service),
    memory: MemoryCoverService = Depends(get_memory_cover_service),
):
    event = get_admin_event_or_404(db, event_token, admin.id)
    event = covers.upload_cover(db, event, file)
    return _invitation_public(event, event_token, covers, music, memory)


@router.delete("/admin/events/{event_token}/invitation/cover", response_model=InvitationPublic)
def admin_delete_cover(
    event_token: str,
    db: Session = Depends(get_db),
    admin: AdminUser = Depends(get_current_admin),
    covers: InvitationCoverService = Depends(get_cover_service),
    music: InvitationMusicService = Depends(get_music_service),
    memory: MemoryCoverService = Depends(get_memory_cover_service),
):
    event = get_admin_event_or_404(db, event_token, admin.id)
    event = covers.remove_cover(db, event)
    return _invitation_public(event, event_token, covers, music, memory)


@router.post("/admin/events/{event_token}/invitation/music", response_model=InvitationPublic)
def admin_upload_music(
    event_token: str,
    file: Annotated[UploadFile, File()],
    db: Session = Depends(get_db),
    admin: AdminUser = Depends(get_current_admin),
    covers: InvitationCoverService = Depends(get_cover_service),
    music: InvitationMusicService = Depends(get_music_service),
    memory: MemoryCoverService = Depends(get_memory_cover_service),
):
    event = get_admin_event_or_404(db, event_token, admin.id)
    event = music.upload_music(db, event, file)
    record_activity(db, event, "Davetiye müziği güncellendi", "sparkle")
    return _invitation_public(event, event_token, covers, music, memory)


@router.delete("/admin/events/{event_token}/invitation/music", response_model=InvitationPublic)
def admin_delete_music(
    event_token: str,
    db: Session = Depends(get_db),
    admin: AdminUser = Depends(get_current_admin),
    covers: InvitationCoverService = Depends(get_cover_service),
    music: InvitationMusicService = Depends(get_music_service),
    memory: MemoryCoverService = Depends(get_memory_cover_service),
):
    event = get_admin_event_or_404(db, event_token, admin.id)
    event = music.remove_music(db, event)
    record_activity(db, event, "Davetiye müziği kaldırıldı", "sparkle")
    return _invitation_public(event, event_token, covers, music, memory)

@router.post("/admin/events/{event_token}/invitation/memory-cover", response_model=InvitationPublic)
def admin_upload_memory_cover(event_token: str, file: Annotated[UploadFile, File()], db: Session = Depends(get_db), admin: AdminUser = Depends(get_current_admin), covers: InvitationCoverService = Depends(get_cover_service), music: InvitationMusicService = Depends(get_music_service), memory: MemoryCoverService = Depends(get_memory_cover_service)):
    event = get_admin_event_or_404(db, event_token, admin.id)
    event = memory.upload(db, event, file)
    return _invitation_public(event, event_token, covers, music, memory)

@router.delete("/admin/events/{event_token}/invitation/memory-cover", response_model=InvitationPublic)
def admin_delete_memory_cover(event_token: str, db: Session = Depends(get_db), admin: AdminUser = Depends(get_current_admin), covers: InvitationCoverService = Depends(get_cover_service), music: InvitationMusicService = Depends(get_music_service), memory: MemoryCoverService = Depends(get_memory_cover_service)):
    event = get_admin_event_or_404(db, event_token, admin.id)
    event = memory.remove(db, event)
    return _invitation_public(event, event_token, covers, music, memory)


@router.get("/admin/contacts", response_model=list[ContactPublic])
def admin_list_contacts(
    db: Session = Depends(get_db),
    admin: AdminUser = Depends(get_current_admin),
):
    return [ContactPublic.model_validate(item) for item in list_contacts(db, admin.id)]


@router.post("/admin/contacts", response_model=ContactPublic, status_code=status.HTTP_201_CREATED)
def admin_create_contact(
    payload: ContactCreate,
    db: Session = Depends(get_db),
    admin: AdminUser = Depends(get_current_admin),
):
    contact = create_contact(db, admin.id, payload.name, str(payload.email))
    return ContactPublic.model_validate(contact)


@router.delete("/admin/contacts/{contact_id}", status_code=status.HTTP_204_NO_CONTENT)
def admin_delete_contact(
    contact_id: str,
    db: Session = Depends(get_db),
    admin: AdminUser = Depends(get_current_admin),
):
    delete_contact(db, admin.id, contact_id)


@router.get("/admin/events/{event_token}/guests.csv")
def export_guests_csv(event_token: str, db: Session = Depends(get_db), admin: AdminUser = Depends(get_current_admin)):
    import csv
    from io import StringIO
    event = get_admin_event_or_404(db, event_token, admin.id, write=False)
    output = StringIO(newline="")
    writer = csv.writer(output)
    writer.writerow(["Ad Soyad", "E-posta", "Durum", "Kişi Sayısı", "Beslenme", "Beslenme Rızası", "Not", "Yanıt Zamanı", "Grup", "Masa", "Telefon"])
    def safe(value):
        value = str(value or "")
        return "'" + value if value.lstrip().startswith(("=", "+", "-", "@")) or value.startswith(("\t", "\r", "\n")) else value
    labels = {"attending": "Katılacak", "declined": "Katılmayacak", "pending": "Bekleniyor"}
    for guest in list_guests(db, event):
        writer.writerow([safe(guest.name), safe(guest.email), labels[guest.status], guest.people,
                         safe(guest.dietary_requirements),
                         guest.dietary_consent_at.isoformat() if guest.dietary_consent_at else "",
                         safe(guest.notes),
                         guest.responded_at.isoformat() if guest.responded_at else "",
                         safe(guest.group_name), safe(guest.table_name), safe(guest.phone)])
    return Response(content=("\ufeff" + output.getvalue()).encode("utf-8"), media_type="text/csv; charset=utf-8",
                    headers={"Content-Disposition": 'attachment; filename="luma-guests.csv"', "Cache-Control": "private, no-store"})


@router.post("/admin/events/{event_token}/guests/{guest_id}/rsvp-link")
def issue_rsvp_link(event_token: str, guest_id: str, db: Session = Depends(get_db), admin: AdminUser = Depends(get_current_admin)):
    import hashlib
    import secrets
    from app.db.models import Guest
    event = get_admin_event_or_404(db, event_token, admin.id)
    guest = db.query(Guest).filter(Guest.event_id == event.id, Guest.id == guest_id).one_or_none()
    if not guest:
        raise HTTPException(status_code=404, detail="Misafir bulunamadı.")
    token = secrets.token_urlsafe(32)
    guest.rsvp_token_hash = hashlib.sha256(token.encode()).hexdigest()
    db.commit()
    return JSONResponse({"edit_token": token}, headers={"Cache-Control": "no-store"})


@router.get("/admin/events/{event_token}/guests/{guest_id}/invite-link")
def get_invite_link(event_token: str, guest_id: str, db: Session = Depends(get_db), admin: AdminUser = Depends(get_current_admin)):
    """The guest's personal link (the part after '#'); the same every time until it is reset."""
    from app.db.models import Guest
    from app.services import guest_access
    event = get_admin_event_or_404(db, event_token, admin.id)
    guest = db.query(Guest).filter(Guest.event_id == event.id, Guest.id == guest_id).one_or_none()
    if not guest:
        raise HTTPException(status_code=404, detail="Misafir bulunamadı.")
    return JSONResponse({"fragment": guest_access.invite_fragment(guest), "device_count": guest.device_count,
                         "device_allowance": guest_access.device_allowance(guest)}, headers={"Cache-Control": "no-store"})


@router.post("/admin/events/{event_token}/guests/{guest_id}/invite-link/sent", response_model=GuestPublic)
def mark_invite_sent(event_token: str, guest_id: str, db: Session = Depends(get_db), admin: AdminUser = Depends(get_current_admin)):
    """The owner sent the personal link (WhatsApp / copy); shown as 'Gönderildi' in the guest list."""
    from datetime import datetime, timezone
    from app.db.models import Guest
    event = get_admin_event_or_404(db, event_token, admin.id)
    guest = db.query(Guest).filter(Guest.event_id == event.id, Guest.id == guest_id).one_or_none()
    if not guest:
        raise HTTPException(status_code=404, detail="Misafir bulunamadı.")
    guest.invite_sent_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(guest)
    return GuestPublic.model_validate(guest)


@router.post("/admin/events/{event_token}/guests/{guest_id}/invite-link/reset")
def reset_invite_link(event_token: str, guest_id: str, db: Session = Depends(get_db), admin: AdminUser = Depends(get_current_admin)):
    """New link for the guest: the old one stops working and their devices must open the new one."""
    from app.db.models import Guest
    from app.services import guest_access
    event = get_admin_event_or_404(db, event_token, admin.id)
    guest = db.query(Guest).filter(Guest.event_id == event.id, Guest.id == guest_id).one_or_none()
    if not guest:
        raise HTTPException(status_code=404, detail="Misafir bulunamadı.")
    guest_access.reset_link(db, guest)
    record_activity(db, event, f"{guest.name} için yeni kişisel bağlantı oluşturuldu", "sparkle")
    return JSONResponse({"fragment": guest_access.invite_fragment(guest), "device_count": 0,
                         "device_allowance": guest_access.device_allowance(guest)}, headers={"Cache-Control": "no-store"})


class SlideshowUpdate(BaseModel):
    photo_ids: list[str] | None = Field(default=None, max_length=5000)
    auto_add: bool | None = None
    transition: Literal["fade", "slide", "zoom", "mix"] | None = None
    seconds: int | None = Field(default=None, ge=3, le=15)
    show_to_guests: bool | None = None
    show_captions: bool | None = None
    title: str | None = Field(default=None, max_length=120)


def _slideshow_admin(db: Session, event):
    from app.api.photos import photo_public
    from app.services import slideshow
    current = slideshow.slides(db, event)
    config = slideshow.settings(event)
    return {
        **{key: config[key] for key in ("auto_add", "transition", "seconds", "show_to_guests", "show_captions", "title")},
        "slides": [photo_public(photo, event.private_token, admin=True).model_dump(mode="json") for photo in current],
        "available": [photo_public(photo, event.private_token, admin=True).model_dump(mode="json")
                      for photo in slideshow.available(db, event, current)],
        "player_path": f"/e/{event.private_token}/slayt",
        "album_public": bool(event.album_public),
    }


@router.get("/admin/events/{event_token}/slideshow")
def admin_get_slideshow(event_token: str, db: Session = Depends(get_db), admin: AdminUser = Depends(get_current_admin)):
    event = get_admin_event_or_404(db, event_token, admin.id, write=False)
    return JSONResponse(_slideshow_admin(db, event), headers={"Cache-Control": "no-store"})


@router.put("/admin/events/{event_token}/slideshow")
def admin_save_slideshow(event_token: str, payload: SlideshowUpdate, db: Session = Depends(get_db), admin: AdminUser = Depends(get_current_admin)):
    from app.services import slideshow
    event = get_admin_event_or_404(db, event_token, admin.id)
    slideshow.save(db, event, payload.model_dump(exclude_unset=True))
    return JSONResponse(_slideshow_admin(db, event), headers={"Cache-Control": "no-store"})


@router.get("/events/{event_token}/slideshow")
def public_slideshow(event_token: str, request: Request, db: Session = Depends(get_db)):
    """The player's data. Guests see it only if the owner allows; the owner's screen always can."""
    from app.api.event_access import _owner_preview_valid
    from app.services import slideshow
    event = get_event_by_token(db, event_token)
    config = slideshow.settings(event)
    if not slideshow.guests_can_watch(event) and not _owner_preview_valid(request, event):
        raise HTTPException(status_code=404, detail="Slayt gösterisi kapalı.")
    items = [{
        "id": photo.id,
        "url": f"/api/photos/{photo.id}?access={event.private_token}",
        "thumbnail_url": f"/api/photos/{photo.id}/thumbnail?access={event.private_token}",
        "width": photo.width, "height": photo.height,
        "uploader_name": photo.uploader_name if config["show_captions"] else "",
        "caption": photo.caption if config["show_captions"] else "",
    } for photo in slideshow.slides(db, event)]
    return JSONResponse({"title": config["title"] or event.name, "transition": config["transition"],
                         "seconds": config["seconds"], "slides": items}, headers={"Cache-Control": "no-store"})


@router.get("/admin/events/{event_token}/members", response_model=list[EventMemberPublic])
def list_event_members(event_token: str, db: Session = Depends(get_db), admin: AdminUser = Depends(get_current_admin)):
    event = get_admin_event_or_404(db, event_token, admin.id, write=False)
    members = [EventMemberPublic(id=event.admin.id, email=event.admin.email,
                                display_name=event.admin.display_name, role="owner",
                                created_at=event.admin.created_at)]
    members.extend(EventMemberPublic(id=item.id, email=item.admin.email,
                                     display_name=item.admin.display_name, role=item.role,
                                     created_at=item.created_at) for item in event.members)
    return members


@router.post("/admin/events/{event_token}/members", response_model=EventMemberPublic, status_code=201)
def add_event_member(event_token: str, payload: EventMemberCreate, db: Session = Depends(get_db), admin: AdminUser = Depends(get_current_admin)):
    from app.db.models import EventMember
    event = get_admin_event_or_404(db, event_token, admin.id, owner=True)
    target = db.query(AdminUser).filter(AdminUser.email == str(payload.email).lower()).one_or_none()
    if not target:
        raise HTTPException(status_code=404, detail="Bu e-posta ile kayıtlı bir yönetici hesabı yok.")
    if target.id == event.admin_id:
        raise HTTPException(status_code=409, detail="Etkinlik sahibi zaten ekipte.")
    member = db.query(EventMember).filter(EventMember.event_id == event.id, EventMember.admin_id == target.id).one_or_none()
    if member:
        raise HTTPException(status_code=409, detail="Bu yönetici zaten ekipte.")
    member = EventMember(event_id=event.id, admin_id=target.id, role=payload.role)
    db.add(member); db.commit(); db.refresh(member)
    return EventMemberPublic(id=member.id, email=target.email, display_name=target.display_name,
                             role=member.role, created_at=member.created_at)


@router.patch("/admin/events/{event_token}/members/{member_id}", response_model=EventMemberPublic)
def change_event_member(event_token: str, member_id: str, payload: EventMemberUpdate, db: Session = Depends(get_db), admin: AdminUser = Depends(get_current_admin)):
    from app.db.models import EventMember
    event = get_admin_event_or_404(db, event_token, admin.id, owner=True)
    member = db.query(EventMember).filter(EventMember.id == member_id, EventMember.event_id == event.id).one_or_none()
    if not member: raise HTTPException(status_code=404, detail="Ekip üyesi bulunamadı.")
    member.role = payload.role; db.commit(); db.refresh(member)
    return EventMemberPublic(id=member.id, email=member.admin.email, display_name=member.admin.display_name,
                             role=member.role, created_at=member.created_at)


@router.delete("/admin/events/{event_token}/members/{member_id}", status_code=204)
def remove_event_member(event_token: str, member_id: str, db: Session = Depends(get_db), admin: AdminUser = Depends(get_current_admin)):
    from app.db.models import EventMember
    event = get_admin_event_or_404(db, event_token, admin.id, owner=True)
    member = db.query(EventMember).filter(EventMember.id == member_id, EventMember.event_id == event.id).one_or_none()
    if not member: raise HTTPException(status_code=404, detail="Ekip üyesi bulunamadı.")
    db.delete(member); db.commit()
