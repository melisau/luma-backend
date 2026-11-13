import io

from PIL import Image

from app.core.config import get_settings
from app.db import database as db_module
from app.db.models import AccountToken, AdminUser, Contact, Event, EventMember, Photo

TOKEN = "event-a-token-123456789012345678901234"


def _jpeg():
    stream = io.BytesIO()
    Image.new("RGB", (60, 40), "red").save(stream, format="JPEG")
    return stream.getvalue()


def _stored_files():
    root = get_settings().local_storage_path
    return [p for p in root.rglob("*") if p.is_file()]


def _count(model, **filters):
    db = db_module.SessionLocal()
    try:
        return db.query(model).filter_by(**filters).count()
    finally:
        db.close()


def _setup_account_with_data(client, admin_headers):
    # A guest photo in the account's own event.
    upload = client.post(
        f"/api/events/{TOKEN}/photos",
        data={"uploader_name": "Misafir"},
        files=[("files", ("a.jpg", _jpeg(), "image/jpeg"))],
    )
    assert upload.status_code == 200
    # A saved contact and a pending password-reset link.
    assert client.post("/api/admin/contacts", headers=admin_headers, json={"name": "Ayşe", "email": "ayse@test.com"}).status_code == 201
    assert client.post("/api/admin/password-reset/request", json={"email": "admin@test.com"}).status_code == 202
    # Someone else's event where this account is a team member.
    other = client.post("/api/admin/register", json={"email": "other@test.com", "password": "otherpassword123"})
    other_headers = {"Authorization": f"Bearer {other.json()['access_token']}"}
    other_event = client.post("/api/admin/events", headers=other_headers, json={"name": "Başkasının etkinliği"}).json()
    other_token = other_event["private_token"]
    member = client.post(
        f"/api/admin/events/{other_token}/members",
        headers=other_headers,
        json={"email": "admin@test.com", "role": "viewer"},
    )
    assert member.status_code == 201
    return other_token, other_headers


def test_wrong_password_deletes_nothing(client, admin_headers):
    response = client.request("DELETE", "/api/admin/me", headers=admin_headers, json={"password": "wrong-password"})
    assert response.status_code == 400
    assert _count(AdminUser, email="admin@test.com") == 1
    assert _count(Event, private_token=TOKEN) == 1


def test_requires_login(client):
    assert client.request("DELETE", "/api/admin/me", json={"password": "testpassword123"}).status_code == 401


def test_delete_account_removes_everything_it_owns(client, admin_headers, monkeypatch):
    from app.api import photos as photos_api

    other_token, other_headers = _setup_account_with_data(client, admin_headers)
    db = db_module.SessionLocal()
    try:
        admin_id = db.query(AdminUser.id).filter_by(email="admin@test.com").scalar()
    finally:
        db.close()
    files_before = _stored_files()
    assert files_before, "the uploaded photo should be on disk"
    assert _count(Photo) == 1

    sent = []
    monkeypatch.setattr(photos_api, "send_email", lambda to, subject, body: sent.append((to, subject)) or True)

    response = client.request("DELETE", "/api/admin/me", headers=admin_headers, json={"password": "testpassword123"})
    assert response.status_code == 204

    assert _count(AdminUser, id=admin_id) == 0
    assert _count(Event, private_token=TOKEN) == 0
    assert _count(Photo) == 0
    assert _count(Contact, admin_id=admin_id) == 0
    assert _count(AccountToken, admin_id=admin_id) == 0
    assert _count(EventMember, admin_id=admin_id) == 0
    assert not any(path.exists() for path in files_before)

    # The other user's event is untouched; only the membership is gone.
    assert _count(Event, private_token=other_token) == 1
    members = client.get(f"/api/admin/events/{other_token}/members", headers=other_headers).json()
    assert [m["email"] for m in members] == ["other@test.com"]

    # The old session and password no longer work; a confirmation email went out.
    assert client.get("/api/admin/me", headers=admin_headers).status_code == 401
    assert client.post("/api/admin/login", json={"email": "admin@test.com", "password": "testpassword123"}).status_code == 401
    assert sent == [("admin@test.com", "Luma Event hesabınız silindi")]


def test_deleted_email_can_register_again(client, admin_headers):
    assert client.request("DELETE", "/api/admin/me", headers=admin_headers, json={"password": "testpassword123"}).status_code == 204
    again = client.post("/api/admin/register", json={"email": "admin@test.com", "password": "newpassword123"})
    assert again.status_code == 201
