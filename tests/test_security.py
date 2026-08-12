import io

import pytest
from PIL import Image

TOKEN = "event-a-token-123456789012345678901234"


def make_image_bytes(fmt="JPEG", size=(800, 600)):
    buffer = io.BytesIO()
    Image.new("RGB", size, color=(120, 80, 90)).save(buffer, format=fmt)
    return buffer.getvalue()


def test_valid_image_upload(client):
    files = [("files", ("photo.jpg", make_image_bytes(), "image/jpeg"))]
    data = {"uploader_name": "Ayşe"}
    response = client.post(f"/api/events/{TOKEN}/photos", data=data, files=files)
    assert response.status_code == 200
    assert len(response.json()["uploaded"]) == 1


def test_invalid_mime(client):
    files = [("files", ("note.txt", b"hello", "text/plain"))]
    response = client.post(
        f"/api/events/{TOKEN}/photos",
        data={"uploader_name": "Ayşe"},
        files=files,
    )
    assert response.status_code == 400


def test_fake_jpg_extension(client):
    files = [("files", ("fake.jpg", b"not-an-image", "image/jpeg"))]
    response = client.post(
        f"/api/events/{TOKEN}/photos",
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
        f"/api/events/{TOKEN}/photos",
        data={"uploader_name": "Ayşe"},
        files=files,
    )
    photo_id = upload.json()["uploaded"][0]["id"]
    wrong_token_response = client.get(f"/api/photos/{photo_id}?access=wrong-token-value")
    assert wrong_token_response.status_code in {401, 404}


def test_private_image_access_requires_token(client, admin_headers):
    files = [("files", ("photo.jpg", make_image_bytes(), "image/jpeg"))]
    upload = client.post(
        f"/api/events/{TOKEN}/photos",
        data={"uploader_name": "Ayşe"},
        files=files,
    )
    photo_id = upload.json()["uploaded"][0]["id"]
    denied = client.get(f"/api/photos/{photo_id}")
    assert denied.status_code == 401
    pending = client.get(f"/api/photos/{photo_id}?access={TOKEN}")
    assert pending.status_code == 404
    client.patch(
        f"/api/admin/photos/{photo_id}",
        headers=admin_headers,
        json={"status": "approved"},
    )
    allowed = client.get(f"/api/photos/{photo_id}?access={TOKEN}")
    assert allowed.status_code == 200
    assert allowed.headers["content-type"].startswith("image/")


def test_admin_can_access_without_guest_token(client, admin_headers):
    files = [("files", ("photo.jpg", make_image_bytes(), "image/jpeg"))]
    upload = client.post(
        f"/api/events/{TOKEN}/photos",
        data={"uploader_name": "Ayşe"},
        files=files,
    )
    photo_id = upload.json()["uploaded"][0]["id"]
    response = client.get(f"/api/photos/{photo_id}", headers=admin_headers)
    assert response.status_code == 200


def test_api_does_not_expose_storage_keys(client, admin_headers):
    files = [("files", ("photo.jpg", make_image_bytes(), "image/jpeg"))]
    upload = client.post(
        f"/api/events/{TOKEN}/photos",
        data={"uploader_name": "Ayşe"},
        files=files,
    )
    photo_id = upload.json()["uploaded"][0]["id"]
    client.patch(
        f"/api/admin/photos/{photo_id}",
        headers=admin_headers,
        json={"status": "approved"},
    )
    listing = client.get(f"/api/events/{TOKEN}/photos")
    payload = listing.json()[0]
    assert "storage_key" not in payload
    assert "bucket" not in payload
