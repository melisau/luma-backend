from typing import Annotated

from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile, status
from fastapi.responses import Response, JSONResponse
from sqlalchemy.orm import Session

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
    guest, edit_token = submit_rsvp(db, event, payload)
    try:
        url=f"{(get_settings().public_base_url or 'http://localhost:5500').rstrip('/')}/e/{event_token}"
        send_email(guest.email,f"{event.name} RSVP onayı",f"Yanıtınız alındı: {guest.people} kişi, durum: {guest.status}. Davetiye: {url}")
    except Exception:
        import logging; logging.getLogger(__name__).exception("RSVP confirmation email failed")
    return RsvpReceipt(**GuestPublic.model_validate(guest).model_dump(), edit_token=edit_token)


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
async def admin_upload_cover(
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
async def admin_upload_music(
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
async def admin_upload_memory_cover(event_token: str, file: Annotated[UploadFile, File()], db: Session = Depends(get_db), admin: AdminUser = Depends(get_current_admin), covers: InvitationCoverService = Depends(get_cover_service), music: InvitationMusicService = Depends(get_music_service), memory: MemoryCoverService = Depends(get_memory_cover_service)):
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
    writer.writerow(["Ad Soyad", "E-posta", "Durum", "Kişi Sayısı", "Beslenme", "Not", "Yanıt Zamanı", "Grup", "Masa"])
    def safe(value):
        value = str(value or "")
        return "'" + value if value.lstrip().startswith(("=", "+", "-", "@")) or value.startswith(("\t", "\r", "\n")) else value
    labels = {"attending": "Katılacak", "declined": "Katılmayacak", "pending": "Bekleniyor"}
    for guest in list_guests(db, event):
        writer.writerow([safe(guest.name), safe(guest.email), labels[guest.status], guest.people,
                         safe(guest.dietary_requirements), safe(guest.notes),
                         guest.responded_at.isoformat() if guest.responded_at else "",
                         safe(guest.group_name), safe(guest.table_name)])
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
