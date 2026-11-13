from datetime import datetime, timedelta, timezone

from app.core.config import get_settings
from app.db import database as db_module
from app.db.models import AdminUser, Event, Guest

TOKEN = "event-a-token-123456789012345678901234"


def _require_verification(monkeypatch):
    monkeypatch.setenv("REQUIRE_VERIFIED_EMAIL", "true")
    get_settings.cache_clear()


def _set_verified(value):
    db = db_module.SessionLocal()
    try:
        admin = db.query(AdminUser).filter(AdminUser.email == "admin@test.com").one()
        admin.email_verified_at = value
        db.commit()
    finally:
        db.close()


def test_unverified_owner_invitation_is_closed(client, monkeypatch):
    _require_verification(monkeypatch)
    _set_verified(None)
    assert client.get(f"/api/events/{TOKEN}").status_code == 403

    _set_verified(datetime.now(timezone.utc))
    assert client.get(f"/api/events/{TOKEN}").status_code == 200


def test_verification_not_required_outside_production(client):
    _set_verified(None)
    assert client.get(f"/api/events/{TOKEN}").status_code == 200


def test_reminders_skip_unverified_owner(client, monkeypatch):
    from app.services import reminder_service

    _require_verification(monkeypatch)
    _set_verified(None)
    db = db_module.SessionLocal()
    try:
        event = db.query(Event).filter(Event.private_token == TOKEN).one()
        event.rsvp_reminder_at = datetime.now(timezone.utc) - timedelta(minutes=1)
        db.add(Guest(event_id=event.id, name="Misafir", email="misafir@test.com"))
        db.commit()
    finally:
        db.close()

    sent = []
    monkeypatch.setattr(reminder_service, "send_email", lambda *args: sent.append(args) or True)
    assert reminder_service.send_due_reminders() == 0
    assert sent == []


def test_registration_has_hourly_limit(client, monkeypatch):
    monkeypatch.setenv("REGISTRATIONS_PER_HOUR", "2")
    monkeypatch.setenv("LOGINS_PER_MINUTE", "100")
    get_settings.cache_clear()
    for index in range(2):
        response = client.post(
            "/api/admin/register",
            json={"email": f"limit{index}@test.com", "password": "testpassword123"},
        )
        assert response.status_code == 201
    blocked = client.post(
        "/api/admin/register",
        json={"email": "limit-extra@test.com", "password": "testpassword123"},
    )
    assert blocked.status_code == 429
