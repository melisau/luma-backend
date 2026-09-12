import logging
from datetime import datetime, timezone

from app.core.config import get_settings
from app.db import database as db_module
from app.db.models import Event, Guest
from app.services.email_service import send_email

logger=logging.getLogger(__name__)

def send_due_reminders() -> int:
    db=db_module.SessionLocal();sent=0
    try:
        now=datetime.now(timezone.utc)
        events=db.query(Event).filter(Event.rsvp_reminder_at.is_not(None),Event.rsvp_reminder_sent_at.is_(None),Event.is_active.is_(True)).all()
        for event in events:
            due=event.rsvp_reminder_at if event.rsvp_reminder_at.tzinfo else event.rsvp_reminder_at.replace(tzinfo=timezone.utc)
            if due>now: continue
            url=f"{(get_settings().public_base_url or 'http://localhost:5500').rstrip('/')}/e/{event.private_token}"
            for guest in db.query(Guest).filter(Guest.event_id==event.id,Guest.status=="pending").all():
                try:
                    if send_email(guest.email,f"{event.name} için RSVP hatırlatması",f"Merhaba {guest.name}, katılım yanıtınızı buradan iletebilirsiniz: {url}"): sent+=1
                except Exception: logger.exception("RSVP reminder failed event=%s",event.id)
            event.rsvp_reminder_sent_at=now;db.commit()
        return sent
    finally: db.close()
