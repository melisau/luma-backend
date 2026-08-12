import io

from PIL import Image

TOKEN = "event-a-token-123456789012345678901234"


def make_image_bytes(fmt="JPEG", size=(800, 600)):
    buffer = io.BytesIO()
    Image.new("RGB", size, color=(120, 80, 90)).save(buffer, format=fmt)
    return buffer.getvalue()


def upload_photo(client, name="Ayşe"):
    files = [("files", ("photo.jpg", make_image_bytes(), "image/jpeg"))]
    response = client.post(
        f"/api/events/{TOKEN}/photos",
        data={"uploader_name": name},
        files=files,
    )
    assert response.status_code == 200
    return response.json()["uploaded"][0]["id"]


def test_upload_starts_as_pending(client, admin_headers):
    photo_id = upload_photo(client)
    admin_list = client.get(f"/api/admin/events/{TOKEN}/photos", headers=admin_headers)
    photo = next(item for item in admin_list.json() if item["id"] == photo_id)
    assert photo["status"] == "uploaded"


def test_guest_list_hides_pending_and_hidden(client, admin_headers):
    pending_id = upload_photo(client, "Pending")
    approved_id = upload_photo(client, "Approved")
    hidden_id = upload_photo(client, "Hidden")

    client.patch(
        f"/api/admin/photos/{approved_id}",
        headers=admin_headers,
        json={"status": "approved"},
    )
    client.patch(
        f"/api/admin/photos/{hidden_id}",
        headers=admin_headers,
        json={"status": "hidden"},
    )

    guest_list = client.get(f"/api/events/{TOKEN}/photos")
    assert guest_list.status_code == 200
    ids = {item["id"] for item in guest_list.json()}
    assert approved_id in ids
    assert pending_id not in ids
    assert hidden_id not in ids


def test_guest_cannot_access_pending_image(client, admin_headers):
    photo_id = upload_photo(client)

    denied = client.get(f"/api/photos/{photo_id}?access={TOKEN}")
    assert denied.status_code == 404

    client.patch(
        f"/api/admin/photos/{photo_id}",
        headers=admin_headers,
        json={"status": "approved"},
    )

    allowed = client.get(f"/api/photos/{photo_id}?access={TOKEN}")
    assert allowed.status_code == 200


def test_hide_removes_guest_access(client, admin_headers):
    photo_id = upload_photo(client)
    client.patch(
        f"/api/admin/photos/{photo_id}",
        headers=admin_headers,
        json={"status": "approved"},
    )
    assert client.get(f"/api/photos/{photo_id}?access={TOKEN}").status_code == 200

    client.patch(
        f"/api/admin/photos/{photo_id}",
        headers=admin_headers,
        json={"status": "hidden"},
    )
    assert client.get(f"/api/photos/{photo_id}?access={TOKEN}").status_code == 404


def test_invalid_status_rejected(client, admin_headers):
    photo_id = upload_photo(client)
    response = client.patch(
        f"/api/admin/photos/{photo_id}",
        headers=admin_headers,
        json={"status": "deleted"},
    )
    assert response.status_code == 422
