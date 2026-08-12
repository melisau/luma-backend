import io
import os
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from PIL import Image

os.environ["DATABASE_URL"] = "sqlite:///:memory:"
os.environ["STORAGE_BACKEND"] = "local"
os.environ["LOCAL_STORAGE_PATH"] = str(Path(__file__).resolve().parent / "tmp_uploads")
os.environ["SECRET_KEY"] = "test-secret-key"
os.environ["ADMIN_EMAIL"] = "admin@test.com"
os.environ["ADMIN_PASSWORD"] = "testpassword123"
os.environ["SEED_EVENT_TOKEN"] = "event-a-token-123456789012345678901234"
os.environ["UPLOADS_PER_MINUTE"] = "100"

from app.core.config import get_settings
from app.db.database import init_db
from app.main import app

get_settings.cache_clear()


@pytest.fixture()
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("LOCAL_STORAGE_PATH", str(tmp_path / "uploads"))
    get_settings.cache_clear()
    init_db()
    with TestClient(app) as test_client:
        yield test_client


def make_image_bytes(fmt="JPEG", size=(800, 600)):
    buffer = io.BytesIO()
    Image.new("RGB", size, color=(120, 80, 90)).save(buffer, format=fmt)
    return buffer.getvalue()


def admin_headers(client):
    response = client.post(
        "/api/admin/login",
        json={"email": "admin@test.com", "password": "testpassword123"},
    )
    token = response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def test_valid_image_upload(client):
    files = [("files", ("photo.jpg", make_image_bytes(), "image/jpeg"))]
    data = {"uploader_name": "Ayşe"}
    response = client.post("/api/events/event-a-token-123456789012345678901234/photos", data=data, files=files)
    assert response.status_code == 200
    assert len(response.json()["uploaded"]) == 1


def test_invalid_mime(client):
    files = [("files", ("note.txt", b"hello", "text/plain"))]
    response = client.post(
        "/api/events/event-a-token-123456789012345678901234/photos",
        data={"uploader_name": "Ayşe"},
        files=files,
    )
    assert response.status_code == 400


def test_fake_jpg_extension(client):
    files = [("files", ("fake.jpg", b"not-an-image", "image/jpeg"))]
    response = client.post(
        "/api/events/event-a-token-123456789012345678901234/photos",
        data={"uploader_name": "Ayşe"},
        files=files,
    )
    assert response.status_code == 400


def test_nonexistent_event_token(client):
    files = [("files", ("photo.jpg", make_image_bytes(), "image/jpeg"))]
    response = client.post(
        "/api/events/does-not-exist-token/photos",
        data={"uploader_name": "Ayşe"},
        files=files,
    )
    assert response.status_code == 404


def test_event_isolation(client):
    files = [("files", ("photo.jpg", make_image_bytes(), "image/jpeg"))]
    upload = client.post(
        "/api/events/event-a-token-123456789012345678901234/photos",
        data={"uploader_name": "Ayşe"},
        files=files,
    )
    photo_id = upload.json()["uploaded"][0]["id"]
    wrong_token_response = client.get(f"/api/photos/{photo_id}?access=wrong-token-value")
    assert wrong_token_response.status_code in {401, 404}


def test_private_image_access_requires_token(client):
    files = [("files", ("photo.jpg", make_image_bytes(), "image/jpeg"))]
    upload = client.post(
        "/api/events/event-a-token-123456789012345678901234/photos",
        data={"uploader_name": "Ayşe"},
        files=files,
    )
    photo_id = upload.json()["uploaded"][0]["id"]
    denied = client.get(f"/api/photos/{photo_id}")
    assert denied.status_code == 401
    allowed = client.get(
        f"/api/photos/{photo_id}?access=event-a-token-123456789012345678901234"
    )
    assert allowed.status_code == 200
    assert allowed.headers["content-type"].startswith("image/")


def test_admin_can_access_without_guest_token(client):
    files = [("files", ("photo.jpg", make_image_bytes(), "image/jpeg"))]
    upload = client.post(
        "/api/events/event-a-token-123456789012345678901234/photos",
        data={"uploader_name": "Ayşe"},
        files=files,
    )
    photo_id = upload.json()["uploaded"][0]["id"]
    response = client.get(f"/api/photos/{photo_id}", headers=admin_headers(client))
    assert response.status_code == 200


def test_api_does_not_expose_storage_keys(client):
    files = [("files", ("photo.jpg", make_image_bytes(), "image/jpeg"))]
    client.post(
        "/api/events/event-a-token-123456789012345678901234/photos",
        data={"uploader_name": "Ayşe"},
        files=files,
    )
    listing = client.get("/api/events/event-a-token-123456789012345678901234/photos")
    payload = listing.json()[0]
    assert "storage_key" not in payload
    assert "bucket" not in payload
