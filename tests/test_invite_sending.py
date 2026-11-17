"""Sending personal links over WhatsApp: guest phone, 'sent' time and 'opened' time."""
import csv
import io

import pytest

from app.schemas.guest import normalize_phone


@pytest.mark.parametrize("raw, expected", [
    ("0532 123 45 67", "+905321234567"),
    ("532 123 4567", "+905321234567"),
    ("+90 (532) 123-45-67", "+905321234567"),
    ("0049 151 2345678", "+491512345678"),
    ("+44 7700 900123", "+447700900123"),
    ("", ""),
    ("   ", ""),
])
def test_phone_is_normalized(raw, expected):
    assert normalize_phone(raw) == expected


@pytest.mark.parametrize("raw", ["123", "abc", "+1234567890123456"])
def test_bad_phone_is_refused(raw):
    with pytest.raises(ValueError):
        normalize_phone(raw)


@pytest.fixture()
def event(client, admin_headers):
    created = client.post("/api/admin/events", headers=admin_headers, json={"name": "WhatsApp Düğünü"}).json()
    return created["private_token"]


def _guest(client, admin_headers, token, **extra):
    body = {"name": "Ayşe", "email": "ayse@example.com", "people": 1, **extra}
    return client.post(f"/api/admin/events/{token}/guests", headers=admin_headers, json=body)


def test_phone_saved_and_edited(client, admin_headers, event):
    created = _guest(client, admin_headers, event, phone="0532 123 45 67")
    assert created.status_code in (200, 201), created.text
    guest = created.json()
    assert guest["phone"] == "+905321234567"
    assert guest["invite_sent_at"] is None and guest["opened_at"] is None
    url = f"/api/admin/events/{event}/guests/{guest['id']}"
    assert client.patch(url, headers=admin_headers, json={"phone": "+44 7700 900123"}).json()["phone"] == "+447700900123"
    assert client.patch(url, headers=admin_headers, json={"phone": "12"}).status_code == 422
    assert client.patch(url, headers=admin_headers, json={"phone": ""}).json()["phone"] == ""


def test_sent_and_opened_are_tracked(client, admin_headers, event):
    guest = _guest(client, admin_headers, event).json()
    base = f"/api/admin/events/{event}/guests/{guest['id']}/invite-link"
    sent = client.post(f"{base}/sent", headers=admin_headers)
    assert sent.status_code == 200 and sent.json()["invite_sent_at"]
    fragment = client.get(base, headers=admin_headers).json()["fragment"]
    guest_id, link_token = fragment.removeprefix("g=").split(".", 1)

    from fastapi.testclient import TestClient
    from app.main import app
    phone = TestClient(app)
    assert phone.post(f"/api/events/{event}/guest-session", json={"guest_id": guest_id, "token": link_token}).status_code == 200

    listed = client.get(f"/api/admin/events/{event}/guests", headers=admin_headers).json()
    row = next(item for item in (listed if isinstance(listed, list) else listed["items"]) if item["id"] == guest["id"])
    assert row["opened_at"] and row["invite_sent_at"]


def test_sent_needs_the_owner(client, admin_headers, event):
    guest = _guest(client, admin_headers, event).json()
    url = f"/api/admin/events/{event}/guests/{guest['id']}/invite-link/sent"
    assert client.post(url).status_code == 401
    assert client.post(f"/api/admin/events/{event}/guests/nope/invite-link/sent", headers=admin_headers).status_code == 404


def test_csv_has_phone_last(client, admin_headers, event):
    _guest(client, admin_headers, event, phone="05321234567")
    response = client.get(f"/api/admin/events/{event}/guests.csv", headers=admin_headers)
    rows = list(csv.reader(io.StringIO(response.content.decode("utf-8-sig"))))
    assert rows[0][-1] == "Telefon"
    assert rows[1][-1].lstrip("'") == "+905321234567"  # formula-safe prefix


def test_migration_is_idempotent(tmp_path):
    import importlib.util
    from pathlib import Path
    import sqlalchemy as sa
    from alembic.migration import MigrationContext
    from alembic.operations import Operations
    path = Path(__file__).parents[1] / "alembic/versions/20261118_0027_guest_phone_invite_sent.py"
    spec = importlib.util.spec_from_file_location("phone_migration", path)
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)
    engine = sa.create_engine(f"sqlite:///{tmp_path / 'legacy.db'}")
    with engine.begin() as connection:
        connection.execute(sa.text("CREATE TABLE guests (id TEXT PRIMARY KEY)"))
        connection.execute(sa.text("INSERT INTO guests VALUES ('g1')"))
        with Operations.context(MigrationContext.configure(connection)):
            migration.upgrade()
            migration.upgrade()
        assert connection.execute(sa.text("SELECT phone FROM guests")).scalar_one() == ""
        assert {"phone", "invite_sent_at"} <= {c["name"] for c in sa.inspect(connection).get_columns("guests")}
    engine.dispose()
