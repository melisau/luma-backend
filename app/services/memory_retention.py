import logging
from datetime import datetime, timezone
from sqlalchemy import select
from app.db import database
from app.db.models import Event, Photo, GuestbookMessage
from app.services.storage import get_storage

logger=logging.getLogger(__name__)


def memories_expired(event, now=None):
    deadline=event.memory_delete_at
    if deadline is None:return False
    if deadline.tzinfo is None:deadline=deadline.replace(tzinfo=timezone.utc)
    return deadline <= (now or datetime.now(timezone.utc))


def purge_expired_memories(now=None):
    """Only explicitly scheduled events are eligible. Failed files remain for retry."""
    now=now or datetime.now(timezone.utc)
    storage=get_storage()
    removed_photos=removed_messages=0
    with database.SessionLocal() as db:
        ids=db.scalars(select(Event.id).where(Event.memory_delete_at<=now,Event.memory_purged_at.is_(None))).all()
    for event_id in ids:
        with database.SessionLocal() as db:
            try:
                event=db.scalars(select(Event).where(Event.id==event_id,Event.memory_delete_at<=now,Event.memory_purged_at.is_(None)).with_for_update(skip_locked=True)).one_or_none()
                if not event:continue
                failed=False
                deleted_count=0
                for photo in db.query(Photo).filter(Photo.event_id==event.id).all():
                    try:
                        storage.delete(photo.storage_key_original)
                        if photo.storage_key_thumb:storage.delete(photo.storage_key_thumb)
                    except Exception:
                        failed=True
                        logger.exception('Memory cleanup failed for photo %s; will retry',photo.id)
                        continue
                    db.delete(photo);deleted_count+=1
                message_count=db.query(GuestbookMessage).filter(GuestbookMessage.event_id==event.id).delete(synchronize_session=False)
                if not failed:event.memory_purged_at=now
                db.commit()
                removed_photos+=deleted_count;removed_messages+=message_count
            except Exception:
                db.rollback()
                logger.exception('Memory policy cleanup failed for event %s; will retry',event_id)
    return {'photos':removed_photos,'messages':removed_messages}
