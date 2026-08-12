from sqlalchemy.orm import Session

from app.db.models import Event, EventActivity

ACTIVITY_LIMIT = 6


def record_activity(db: Session, event: Event, text: str, kind: str = "check") -> EventActivity:
    item = EventActivity(event_id=event.id, text=text.strip()[:512], kind=kind)
    db.add(item)
    db.commit()
    db.refresh(item)
    _trim_old_activities(db, event.id)
    return item


def list_activities(db: Session, event: Event, limit: int = ACTIVITY_LIMIT) -> list[EventActivity]:
    return (
        db.query(EventActivity)
        .filter(EventActivity.event_id == event.id)
        .order_by(EventActivity.created_at.desc())
        .limit(limit)
        .all()
    )


def _trim_old_activities(db: Session, event_id: str, keep: int = 50) -> None:
    ids = (
        db.query(EventActivity.id)
        .filter(EventActivity.event_id == event_id)
        .order_by(EventActivity.created_at.desc())
        .offset(keep)
        .all()
    )
    if not ids:
        return
    stale = [row[0] for row in ids]
    db.query(EventActivity).filter(EventActivity.id.in_(stale)).delete(synchronize_session=False)
    db.commit()
