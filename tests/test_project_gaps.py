import csv
import io
import pytest

TOKEN = "event-a-token-123456789012345678901234"


def test_logistics_and_timezone_roundtrip(client, admin_headers):
    fields = dict(address="Bebek, İstanbul", transport_notes="18:00 servis", contact_info="Deniz: 0555", schedule="18:00 Karşılama\n19:00 Tören", event_date="2027-06-20T19:30:00+03:00")
    url = f"/api/admin/events/{TOKEN}/invitation"
    assert client.patch(url, headers=admin_headers, json=fields).status_code == 200
    public = client.get(f"/api/events/{TOKEN}/invitation").json()
    for key in fields.keys() - {"event_date"}:
        assert public[key] == fields[key]
    assert public["event_date"] == "2027-06-20T16:30:00Z"
    assert client.patch(url, headers=admin_headers, json={"event_date": public["event_date"]}).status_code == 200
    assert client.get(url, headers=admin_headers).json()["event_date"] == public["event_date"]
    assert client.patch(url, headers=admin_headers, json={"schedule": "x"*3001}).status_code == 422


def test_csv_private_unicode_and_formula_safe(client, admin_headers):
    client.post(f"/api/events/{TOKEN}/rsvp", json={"name":"=1+1", "email":"deniz@example.com", "status":"attending", "people":2, "notes":"İstanbul, Türkiye\nİkinci satır"})
    url = f"/api/admin/events/{TOKEN}/guests.csv"
    assert client.get(url).status_code == 401
    response = client.get(url, headers=admin_headers)
    assert response.status_code == 200
    assert response.content.startswith(b"\xef\xbb\xbf")
    rows = list(csv.reader(io.StringIO(response.content.decode("utf-8-sig"))))
    assert rows[1][0] == "'=1+1"
    assert rows[1][5] == "İstanbul, Türkiye\nİkinci satır"
    assert response.headers["cache-control"] == "private, no-store"
    from app.db import database
    from app.db.models import AdminUser, Event
    from app.core.security import hash_password
    with database.SessionLocal() as db:
        other = AdminUser(email="other@example.com", password_hash=hash_password("SomePass123!"))
        db.add(other); db.flush()
        db.add(Event(admin_id=other.id, name="Other", slug="other", private_token="other-private-event-token-1234567890")); db.commit()
    assert client.get("/api/admin/events/other-private-event-token-1234567890/guests.csv", headers=admin_headers).status_code == 404


def test_rsvp_rate_limit(client, monkeypatch):
    from app.core.config import get_settings
    monkeypatch.setattr(get_settings(), "rsvps_per_minute", 2)
    payload = {"name":"Deniz", "email":"deniz@example.com", "status":"attending"}
    first = client.post(f"/api/events/{TOKEN}/rsvp", json=payload)
    assert first.status_code == 200
    payload["edit_token"] = first.json()["edit_token"]
    assert client.post(f"/api/events/{TOKEN}/rsvp", json=payload).status_code == 200
    assert client.post(f"/api/events/{TOKEN}/rsvp", json=payload).status_code == 429


def test_migration_failure_is_not_swallowed(client, monkeypatch):
    from app.db.database import run_alembic_migrations
    from alembic import command
    def fail(*args, **kwargs):
        raise RuntimeError("migration failed")
    monkeypatch.setattr(command, "upgrade", fail)
    with pytest.raises(RuntimeError, match="migration failed"):
        run_alembic_migrations()
