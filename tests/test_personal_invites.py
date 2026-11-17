"""Personal invitation links: a forwarded link must not open the invitation for someone else."""
import re
from datetime import datetime, timedelta, timezone

import pytest

OPEN_TOKEN = "event-a-token-123456789012345678901234"


@pytest.fixture()
def outbox(monkeypatch):
    sent = []
    import app.services.email_service as email_service
    monkeypatch.setattr(email_service, "send_email", lambda to, subject, body: sent.append((to, subject, body)) or True)
    return sent


@pytest.fixture()
def personal(client, admin_headers):
    event = client.post("/api/admin/events", headers=admin_headers, json={"name": "Kişiye Özel Düğün"}).json()
    token = event["private_token"]
    guest = client.post(f"/api/admin/events/{token}/guests", headers=admin_headers,
                        json={"name": "Ayşe", "email": "ayse@example.com", "people": 2}).json()
    link = client.get(f"/api/admin/events/{token}/guests/{guest['id']}/invite-link", headers=admin_headers).json()
    guest_id, link_token = link["fragment"].removeprefix("g=").split(".", 1)
    client.cookies.clear()  # from here on, the client is a guest's browser
    return {"event": event, "token": token, "guest": guest, "guest_id": guest_id, "link_token": link_token}


def _device(client):
    from fastapi.testclient import TestClient
    from app.main import app
    return TestClient(app)


def _open(device, p, code=None):
    body = {"guest_id": p["guest_id"], "token": p["link_token"]}
    if code:
        body["code"] = code
    return device.post(f"/api/events/{p['token']}/guest-session", json=body)


def test_new_events_are_personal(client, admin_headers, personal):
    assert personal["event"]["invite_mode"] == "personal"
    assert personal["event"]["upload_key"]
    blocked = client.get(f"/api/events/{personal['token']}/invitation")
    assert blocked.status_code == 401
    assert blocked.headers["x-luma-access"] == "personal"
    for path in ("", "/messages", "/photos", "/cover"):
        assert client.get(f"/api/events/{personal['token']}{path}").status_code == 401


def test_link_is_stable_until_reset(client, admin_headers, personal):
    url = f"/api/admin/events/{personal['token']}/guests/{personal['guest_id']}/invite-link"
    again = client.get(url, headers=admin_headers).json()["fragment"]
    assert again == f"g={personal['guest_id']}.{personal['link_token']}"
    client.cookies.clear()


def test_guest_link_opens_on_their_devices(client, personal):
    first = _open(client, personal)
    assert first.status_code == 200
    assert first.json()["guest"]["email"] == "ayse@example.com"
    assert client.get(f"/api/events/{personal['token']}/invitation").status_code == 200
    # Party of 2: a second phone opens without a code.
    second = _device(client)
    assert _open(second, personal).status_code == 200
    assert second.get(f"/api/events/{personal['token']}/invitation").status_code == 200


def test_forwarded_link_needs_the_guests_email_code(client, personal, outbox):
    assert _open(client, personal).status_code == 200
    assert _open(_device(client), personal).status_code == 200
    stranger = _device(client)
    asked = _open(stranger, personal)
    assert asked.status_code == 403
    body = asked.json()
    assert body["code_required"] is True
    assert body["email_hint"] == "a***@e***.com"
    assert stranger.get(f"/api/events/{personal['token']}/invitation").status_code == 401
    to, subject, mail = outbox[-1]
    assert to == "ayse@example.com"
    code = re.search(r"\b(\d{6})\b", mail).group(1)
    wrong = _open(stranger, personal, code="000000" if code != "000000" else "111111")
    assert wrong.status_code == 403
    assert _open(stranger, personal, code=code).status_code == 200
    assert stranger.get(f"/api/events/{personal['token']}/invitation").status_code == 200


def test_code_locks_after_too_many_wrong_tries(client, personal, outbox):
    _open(client, personal); _open(_device(client), personal)
    stranger = _device(client)
    _open(stranger, personal)
    code = re.search(r"\b(\d{6})\b", outbox[-1][2]).group(1)
    for _ in range(5):
        _open(stranger, personal, code="99999" + ("8" if code.endswith("9") else "9"))
    assert _open(stranger, personal, code=code).status_code == 403


def test_wrong_or_reset_link_is_refused(client, admin_headers, personal):
    assert client.post(f"/api/events/{personal['token']}/guest-session",
                       json={"guest_id": personal["guest_id"], "token": "x" * 32}).status_code == 403
    assert _open(client, personal).status_code == 200
    owner = _device(client)
    reset = owner.post(f"/api/admin/events/{personal['token']}/guests/{personal['guest_id']}/invite-link/reset",
                       headers=admin_headers)
    assert reset.status_code == 200 and reset.json()["fragment"] != f"g={personal['guest_id']}.{personal['link_token']}"
    # The old link and the devices it opened stop working at once.
    assert client.get(f"/api/events/{personal['token']}/invitation").status_code == 401
    assert _open(_device(client), personal).status_code == 403


def test_rsvp_updates_the_link_guest_only(client, admin_headers, personal):
    _open(client, personal)
    answer = client.post(f"/api/events/{personal['token']}/rsvp",
                         json={"name": "Ayşe Y.", "email": "baska@example.com", "status": "attending", "people": 2})
    assert answer.status_code == 200
    assert answer.json()["id"] == personal["guest_id"]
    assert answer.json()["email"] == "ayse@example.com"
    assert answer.json()["edit_token"] == ""
    owner = _device(client)
    guests = owner.get(f"/api/admin/events/{personal['token']}/guests", headers=admin_headers).json()
    assert [g["email"] for g in guests] == ["ayse@example.com"]
    assert guests[0]["status"] == "attending" and guests[0]["device_count"] == 1


def test_no_new_guests_without_a_link(client, admin_headers, personal):
    from app.db import database
    from app.services.event_data_service import submit_rsvp
    from app.db.models import Event
    from app.schemas.guest import RsvpSubmit
    from fastapi import HTTPException
    with database.SessionLocal() as db:
        event = db.query(Event).filter(Event.private_token == personal["token"]).one()
        with pytest.raises(HTTPException) as refused:
            submit_rsvp(db, event, RsvpSubmit(name="X", email="x@example.com", status="attending"))
        assert refused.value.status_code == 403


def test_venue_qr_key_allows_only_upload_on_event_days(client, admin_headers, personal):
    key = {"X-Upload-Key": personal["event"]["upload_key"]}
    base = f"/api/events/{personal['token']}"
    assert client.get(f"{base}/invitation", headers=key).status_code == 200
    upload = client.post(f"{base}/photos", headers=key, data={"uploader_name": "Misafir"},
                         files={"files": ("a.txt", b"not an image", "text/plain")})
    assert upload.status_code not in (401, 403)  # past the access check; rejected only as a bad file
    for path in ("/photos", "/messages"):
        assert client.get(f"{base}{path}", headers=key).status_code == 401
    assert client.post(f"{base}/rsvp", headers=key, json={"name": "X", "email": "x@example.com", "status": "attending"}).status_code == 401
    assert client.get(f"{base}/invitation", headers={"X-Upload-Key": "wrong"}).status_code == 401
    # A month after the event the QR stops working.
    owner = _device(client)
    owner.patch(f"/api/admin/events/{personal['token']}", headers=admin_headers,
                json={"event_date": (datetime.now(timezone.utc) - timedelta(days=30)).isoformat()})
    assert client.get(f"{base}/invitation", headers=key).status_code == 401


def test_owner_preview_and_mode_switch(client, admin_headers, personal):
    owner = _device(client)
    assert owner.post(f"/api/admin/events/{personal['token']}/access-preview", headers=admin_headers).status_code == 200
    assert owner.get(f"/api/events/{personal['token']}/invitation").status_code == 200
    switched = owner.patch(f"/api/admin/events/{personal['token']}", headers=admin_headers, json={"invite_mode": "open"})
    assert switched.status_code == 200 and switched.json()["invite_mode"] == "open"
    assert client.get(f"/api/events/{personal['token']}/invitation").status_code == 200
    old_key = personal["event"]["upload_key"]
    renewed = owner.patch(f"/api/admin/events/{personal['token']}", headers=admin_headers, json={"reset_upload_key": True}).json()
    assert renewed["upload_key"] and renewed["upload_key"] != old_key


def test_open_events_keep_working(client):
    assert client.get(f"/api/events/{OPEN_TOKEN}/invitation").status_code == 200
    assert client.post(f"/api/events/{OPEN_TOKEN}/guest-session", json={"guest_id": "x", "token": "y"}).json() == {"mode": "open"}


def test_uploads_are_rate_limited_per_guest_not_per_wifi(client, personal, monkeypatch):
    from app.api import photos
    seen = []
    monkeypatch.setattr(photos, "enforce_upload_rate_limit", lambda key, token: seen.append(key))
    _open(client, personal)
    client.post(f"/api/events/{personal['token']}/photos", data={"uploader_name": "Ayşe"},
                files={"files": ("a.txt", b"x", "text/plain")})
    assert seen == [f"guest:{personal['guest_id']}"]


def test_personal_invites_migration_is_idempotent(tmp_path):
    import importlib.util
    from pathlib import Path
    import sqlalchemy as sa
    from alembic.migration import MigrationContext
    from alembic.operations import Operations
    path = Path(__file__).parents[1] / "alembic/versions/20261117_0025_personal_invites.py"
    spec = importlib.util.spec_from_file_location("personal_migration", path)
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)
    engine = sa.create_engine(f"sqlite:///{tmp_path / 'legacy.db'}")
    with engine.begin() as connection:
        connection.execute(sa.text("CREATE TABLE events (id TEXT PRIMARY KEY)"))
        connection.execute(sa.text("CREATE TABLE guests (id TEXT PRIMARY KEY)"))
        connection.execute(sa.text("INSERT INTO events VALUES ('e1')"))
        with Operations.context(MigrationContext.configure(connection)):
            migration.upgrade()
            migration.upgrade()
        assert connection.execute(sa.text("SELECT invite_mode FROM events")).scalar_one() == "open"
        assert sa.inspect(connection).has_table("guest_devices")
    engine.dispose()
