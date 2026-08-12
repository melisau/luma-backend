from typing import Annotated

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from fastapi.responses import Response
from sqlalchemy.orm import Session

from app.api.photos import get_current_admin, get_event_by_token
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
    RsvpSubmit,
)
from app.schemas.invitation import InvitationPublic, InvitationUpdateAdmin
from app.services.activity_service import list_activities, record_activity
from app.services.event_data_service import (
    create_contact,
    create_guest_admin,
    create_message,
    delete_contact,
    delete_guest_admin,
    delete_message_admin,
    get_event_or_404,
    invitation_to_public,
    list_contacts,
    list_guests,
    list_messages,
    submit_rsvp,
    update_guest_admin,
    update_invitation_admin,
)
from app.services.invitation_cover_service import InvitationCoverService
from app.services.invitation_music_service import InvitationMusicService

router = APIRouter(tags=["event-data"])


def get_cover_service() -> InvitationCoverService:
    return InvitationCoverService()


def get_music_service() -> InvitationMusicService:
    return InvitationMusicService()


def _cover_url(event, token: str, covers: InvitationCoverService) -> str | None:
    if not event.cover_storage_key:
        return None
    return covers.cover_url(event, token)


def _music_url(event, token: str, music: InvitationMusicService) -> str | None:
    if not event.music_storage_key:
        return None
    return music.music_url(event, token)


def _invitation_public(event, token: str, covers: InvitationCoverService, music: InvitationMusicService):
    return invitation_to_public(
        event,
        _cover_url(event, token, covers),
        _music_url(event, token, music),
    )


@router.get("/events/{event_token}/invitation", response_model=InvitationPublic)
def get_public_invitation(
    event_token: str,
    db: Session = Depends(get_db),
    covers: InvitationCoverService = Depends(get_cover_service),
    music: InvitationMusicService = Depends(get_music_service),
):
    event = get_event_or_404(db, event_token)
    return _invitation_public(event, event_token, covers, music)


@router.get("/events/{event_token}/cover")
def get_public_cover(
    event_token: str,
    db: Session = Depends(get_db),
    covers: InvitationCoverService = Depends(get_cover_service),
):
    event = get_event_or_404(db, event_token)
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
    event = get_event_or_404(db, event_token)
    data, content_type = music.stream_music(event)
    return Response(
        content=data,
        media_type=content_type,
        headers={"Cache-Control": "private, no-store"},
    )


@router.post("/events/{event_token}/rsvp", response_model=GuestPublic)
def public_rsvp(
    event_token: str,
    payload: RsvpSubmit,
    db: Session = Depends(get_db),
):
    event = get_event_by_token(db, event_token)
    guest = submit_rsvp(db, event, payload)
    return GuestPublic.model_validate(guest)


@router.get("/events/{event_token}/messages", response_model=list[GuestbookMessagePublic])
def list_public_messages(event_token: str, db: Session = Depends(get_db)):
    event = get_event_by_token(db, event_token)
    return [GuestbookMessagePublic.model_validate(item) for item in list_messages(db, event)]


@router.post("/events/{event_token}/messages", response_model=GuestbookMessagePublic)
def create_public_message(
    event_token: str,
    payload: GuestbookMessageCreate,
    db: Session = Depends(get_db),
):
    event = get_event_by_token(db, event_token)
    item = create_message(db, event, payload.name, payload.message)
    return GuestbookMessagePublic.model_validate(item)


@router.get("/admin/events/{event_token}/guests", response_model=list[GuestPublic])
def admin_list_guests(
    event_token: str,
    db: Session = Depends(get_db),
    _admin: AdminUser = Depends(get_current_admin),
):
    event = get_event_or_404(db, event_token)
    return [GuestPublic.model_validate(item) for item in list_guests(db, event)]


@router.post("/admin/events/{event_token}/guests", response_model=GuestPublic, status_code=status.HTTP_201_CREATED)
def admin_create_guest(
    event_token: str,
    payload: GuestCreateAdmin,
    db: Session = Depends(get_db),
    _admin: AdminUser = Depends(get_current_admin),
):
    event = get_event_or_404(db, event_token)
    guest = create_guest_admin(db, event, payload)
    return GuestPublic.model_validate(guest)


@router.patch("/admin/events/{event_token}/guests/{guest_id}", response_model=GuestPublic)
def admin_update_guest(
    event_token: str,
    guest_id: str,
    payload: GuestUpdateAdmin,
    db: Session = Depends(get_db),
    _admin: AdminUser = Depends(get_current_admin),
):
    event = get_event_or_404(db, event_token)
    guest = update_guest_admin(db, event, guest_id, payload)
    return GuestPublic.model_validate(guest)


@router.delete("/admin/events/{event_token}/guests/{guest_id}", status_code=status.HTTP_204_NO_CONTENT)
def admin_delete_guest(
    event_token: str,
    guest_id: str,
    db: Session = Depends(get_db),
    _admin: AdminUser = Depends(get_current_admin),
):
    event = get_event_or_404(db, event_token)
    delete_guest_admin(db, event, guest_id)


@router.get("/admin/events/{event_token}/messages", response_model=list[GuestbookMessagePublic])
def admin_list_messages(
    event_token: str,
    db: Session = Depends(get_db),
    _admin: AdminUser = Depends(get_current_admin),
):
    event = get_event_or_404(db, event_token)
    return [GuestbookMessagePublic.model_validate(item) for item in list_messages(db, event)]


@router.delete("/admin/events/{event_token}/messages/{message_id}", status_code=status.HTTP_204_NO_CONTENT)
def admin_delete_message(
    event_token: str,
    message_id: str,
    db: Session = Depends(get_db),
    _admin: AdminUser = Depends(get_current_admin),
):
    event = get_event_or_404(db, event_token)
    delete_message_admin(db, event, message_id)


@router.get("/admin/events/{event_token}/activities", response_model=list[ActivityPublic])
def admin_list_activities(
    event_token: str,
    db: Session = Depends(get_db),
    _admin: AdminUser = Depends(get_current_admin),
):
    event = get_event_or_404(db, event_token)
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
    _admin: AdminUser = Depends(get_current_admin),
):
    event = get_event_or_404(db, event_token)
    item = record_activity(db, event, payload.text, payload.kind)
    return ActivityPublic.model_validate(item)


@router.get("/admin/events/{event_token}/invitation", response_model=InvitationPublic)
def admin_get_invitation(
    event_token: str,
    db: Session = Depends(get_db),
    _admin: AdminUser = Depends(get_current_admin),
    covers: InvitationCoverService = Depends(get_cover_service),
    music: InvitationMusicService = Depends(get_music_service),
):
    event = get_event_or_404(db, event_token)
    return _invitation_public(event, event_token, covers, music)


@router.patch("/admin/events/{event_token}/invitation", response_model=InvitationPublic)
def admin_update_invitation(
    event_token: str,
    payload: InvitationUpdateAdmin,
    db: Session = Depends(get_db),
    _admin: AdminUser = Depends(get_current_admin),
    covers: InvitationCoverService = Depends(get_cover_service),
    music: InvitationMusicService = Depends(get_music_service),
):
    event = get_event_or_404(db, event_token)
    event = update_invitation_admin(db, event, payload)
    return _invitation_public(event, event_token, covers, music)


@router.post("/admin/events/{event_token}/invitation/cover", response_model=InvitationPublic)
async def admin_upload_cover(
    event_token: str,
    file: Annotated[UploadFile, File()],
    db: Session = Depends(get_db),
    _admin: AdminUser = Depends(get_current_admin),
    covers: InvitationCoverService = Depends(get_cover_service),
    music: InvitationMusicService = Depends(get_music_service),
):
    event = get_event_or_404(db, event_token)
    event = covers.upload_cover(db, event, file)
    return _invitation_public(event, event_token, covers, music)


@router.delete("/admin/events/{event_token}/invitation/cover", response_model=InvitationPublic)
def admin_delete_cover(
    event_token: str,
    db: Session = Depends(get_db),
    _admin: AdminUser = Depends(get_current_admin),
    covers: InvitationCoverService = Depends(get_cover_service),
    music: InvitationMusicService = Depends(get_music_service),
):
    event = get_event_or_404(db, event_token)
    event = covers.remove_cover(db, event)
    return _invitation_public(event, event_token, covers, music)


@router.post("/admin/events/{event_token}/invitation/music", response_model=InvitationPublic)
async def admin_upload_music(
    event_token: str,
    file: Annotated[UploadFile, File()],
    db: Session = Depends(get_db),
    _admin: AdminUser = Depends(get_current_admin),
    covers: InvitationCoverService = Depends(get_cover_service),
    music: InvitationMusicService = Depends(get_music_service),
):
    event = get_event_or_404(db, event_token)
    event = music.upload_music(db, event, file)
    record_activity(db, event, "Davetiye müziği güncellendi", "sparkle")
    return _invitation_public(event, event_token, covers, music)


@router.delete("/admin/events/{event_token}/invitation/music", response_model=InvitationPublic)
def admin_delete_music(
    event_token: str,
    db: Session = Depends(get_db),
    _admin: AdminUser = Depends(get_current_admin),
    covers: InvitationCoverService = Depends(get_cover_service),
    music: InvitationMusicService = Depends(get_music_service),
):
    event = get_event_or_404(db, event_token)
    event = music.remove_music(db, event)
    record_activity(db, event, "Davetiye müziği kaldırıldı", "sparkle")
    return _invitation_public(event, event_token, covers, music)


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
