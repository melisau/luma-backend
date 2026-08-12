from datetime import datetime, timezone

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.db.models import Contact, Event, Guest, GuestSource, GuestbookMessage, GuestStatus, MessageStatus, utc_now
from app.schemas.guest import GuestCreateAdmin, GuestUpdateAdmin, RsvpSubmit
from app.schemas.invitation import InvitationUpdateAdmin
from app.services.activity_service import record_activity

STATUS_LABELS = {
    GuestStatus.ATTENDING.value: "Gelecek",
    GuestStatus.DECLINED.value: "Gelmeyecek",
    GuestStatus.PENDING.value: "Cevap bekleniyor",
}


def normalize_email(value: str) -> str:
    return value.strip().lower()


def get_event_or_404(db: Session, event_token: str) -> Event:
    event = db.query(Event).filter(Event.private_token == event_token).one_or_none()
    if not event:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Etkinlik bulunamadı.")
    return event


def list_guests(db: Session, event: Event) -> list[Guest]:
    return db.query(Guest).filter(Guest.event_id == event.id).order_by(Guest.created_at.desc()).all()


def create_guest_admin(db: Session, event: Event, payload: GuestCreateAdmin) -> Guest:
    email = normalize_email(payload.email)
    existing = (
        db.query(Guest)
        .filter(Guest.event_id == event.id, Guest.email == email)
        .one_or_none()
    )
    if existing:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Bu e-posta zaten misafir listesinde.")
    guest = Guest(
        event_id=event.id,
        name=payload.name.strip(),
        email=email,
        status=payload.status,
        people=payload.people,
        source=payload.source,
    )
    db.add(guest)
    db.commit()
    db.refresh(guest)
    record_activity(db, event, f"{guest.name} misafir listesine eklendi", "userplus")
    return guest


def update_guest_admin(db: Session, event: Event, guest_id: str, payload: GuestUpdateAdmin) -> Guest:
    guest = db.query(Guest).filter(Guest.id == guest_id, Guest.event_id == event.id).one_or_none()
    if not guest:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Misafir bulunamadı.")
    if payload.email is not None:
        email = normalize_email(payload.email)
        conflict = (
            db.query(Guest)
            .filter(Guest.event_id == event.id, Guest.email == email, Guest.id != guest.id)
            .one_or_none()
        )
        if conflict:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Bu e-posta zaten misafir listesinde.")
        guest.email = email
    if payload.name is not None:
        guest.name = payload.name.strip()
    if payload.status is not None:
        guest.status = payload.status
    if payload.people is not None:
        guest.people = payload.people
    db.commit()
    db.refresh(guest)
    return guest


def delete_guest_admin(db: Session, event: Event, guest_id: str) -> None:
    guest = db.query(Guest).filter(Guest.id == guest_id, Guest.event_id == event.id).one_or_none()
    if not guest:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Misafir bulunamadı.")
    db.delete(guest)
    db.commit()


def submit_rsvp(db: Session, event: Event, payload: RsvpSubmit) -> Guest:
    if not event.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Bu etkinlik artık aktif değil.")
    email = normalize_email(payload.email)
    guest = (
        db.query(Guest)
        .filter(Guest.event_id == event.id, Guest.email == email)
        .one_or_none()
    )
    now = utc_now()
    created = guest is None
    if guest:
        guest.name = payload.name.strip()
        guest.status = payload.status
        guest.people = payload.people
        guest.responded_at = now
    else:
        guest = Guest(
            event_id=event.id,
            name=payload.name.strip(),
            email=email,
            status=payload.status,
            people=payload.people,
            source=GuestSource.EXTERNAL.value,
            responded_at=now,
        )
        db.add(guest)
    db.commit()
    db.refresh(guest)
    status_label = STATUS_LABELS.get(payload.status, payload.status)
    if created:
        text = f"{guest.name}, listede olmadan davet linkinden yanıt verdi"
    else:
        text = f"{guest.name} katılım durumunu “{status_label}” olarak güncelledi"
    record_activity(db, event, text, "check")
    return guest


def list_messages(db: Session, event: Event, *, approved_only: bool = False) -> list[GuestbookMessage]:
    query = db.query(GuestbookMessage).filter(GuestbookMessage.event_id == event.id)
    if approved_only:
        query = query.filter(GuestbookMessage.status == MessageStatus.APPROVED.value)
    return query.order_by(GuestbookMessage.created_at.desc()).all()


def create_message(db: Session, event: Event, name: str, message: str) -> GuestbookMessage:
    if not event.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Bu etkinlik artık aktif değil.")
    item = GuestbookMessage(
        event_id=event.id,
        name=name.strip(),
        message=message.strip(),
        status=MessageStatus.PENDING.value,
    )
    db.add(item)
    db.commit()
    db.refresh(item)
    record_activity(db, event, f"{item.name} anı defterine yazdı (onay bekliyor)", "book")
    return item


def update_message_admin(
    db: Session,
    event: Event,
    message_id: str,
    status: str,
) -> GuestbookMessage:
    allowed = {
        MessageStatus.PENDING.value,
        MessageStatus.APPROVED.value,
        MessageStatus.HIDDEN.value,
    }
    if status not in allowed:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Geçersiz mesaj durumu.")
    item = (
        db.query(GuestbookMessage)
        .filter(GuestbookMessage.id == message_id, GuestbookMessage.event_id == event.id)
        .one_or_none()
    )
    if not item:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Mesaj bulunamadı.")
    item.status = status
    db.commit()
    db.refresh(item)
    if status == MessageStatus.APPROVED.value:
        record_activity(db, event, f"{item.name} mesajı onaylandı", "book")
    return item


def delete_message_admin(db: Session, event: Event, message_id: str) -> None:
    item = (
        db.query(GuestbookMessage)
        .filter(GuestbookMessage.id == message_id, GuestbookMessage.event_id == event.id)
        .one_or_none()
    )
    if not item:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Mesaj bulunamadı.")
    db.delete(item)
    db.commit()


def invitation_to_public(
    event: Event,
    cover_url: str | None = None,
    music_url: str | None = None,
):
    from app.schemas.invitation import InvitationPublic

    return InvitationPublic(
        name=event.name,
        slug=event.slug,
        event_date=event.event_date,
        venue=event.venue or "",
        city=event.city or "",
        tagline=event.tagline or "",
        story_title=event.story_title or "",
        story_text=event.story_text or "",
        guest_note=event.guest_note or "",
        cover_url=cover_url,
        music_url=music_url,
        music_filename=event.music_filename,
    )


def update_invitation_admin(db: Session, event: Event, payload: InvitationUpdateAdmin) -> Event:
    data = payload.model_dump(exclude_unset=True)
    for key, value in data.items():
        setattr(event, key, value)
    db.commit()
    db.refresh(event)
    return event


def list_contacts(db: Session, admin_id: str) -> list[Contact]:
    return db.query(Contact).filter(Contact.admin_id == admin_id).order_by(Contact.created_at.desc()).all()


def create_contact(db: Session, admin_id: str, name: str, email: str) -> Contact:
    normalized = normalize_email(email)
    existing = (
        db.query(Contact)
        .filter(Contact.admin_id == admin_id, Contact.email == normalized)
        .one_or_none()
    )
    if existing:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Bu e-posta rehberde zaten kayıtlı.")
    contact = Contact(admin_id=admin_id, name=name.strip(), email=normalized)
    db.add(contact)
    db.commit()
    db.refresh(contact)
    return contact


def delete_contact(db: Session, admin_id: str, contact_id: str) -> None:
    contact = (
        db.query(Contact)
        .filter(Contact.id == contact_id, Contact.admin_id == admin_id)
        .one_or_none()
    )
    if not contact:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Kişi bulunamadı.")
    db.delete(contact)
    db.commit()
