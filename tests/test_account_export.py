import io
import json

from PIL import Image

TOKEN = "event-a-token-123456789012345678901234"


def _all_keys(value):
    if isinstance(value, dict):
        for key, inner in value.items():
            yield key
            yield from _all_keys(inner)
    elif isinstance(value, list):
        for inner in value:
            yield from _all_keys(inner)


def _jpeg():
    stream = io.BytesIO()
    Image.new("RGB", (40, 30), "blue").save(stream, format="JPEG")
    return stream.getvalue()


def test_export_requires_login(client):
    assert client.get("/api/admin/me/export").status_code == 401


def test_export_contains_the_accounts_data_and_no_secrets(client, admin_headers):
    client.post(f"/api/admin/events/{TOKEN}/guests", headers=admin_headers, json={"name": "Zeynep", "email": "zeynep@test.com", "dietary_requirements": "Vejetaryen"})
    client.post(f"/api/events/{TOKEN}/messages", json={"name": "Zeynep", "message": "Çok güzeldi!"})
    client.post(f"/api/events/{TOKEN}/photos", data={"uploader_name": "Zeynep"}, files=[("files", ("a.jpg", _jpeg(), "image/jpeg"))])
    client.post("/api/admin/contacts", headers=admin_headers, json={"name": "Ayşe", "email": "ayse@test.com"})
    other = client.post("/api/admin/register", json={"email": "other@test.com", "password": "otherpassword123"})
    other_headers = {"Authorization": f"Bearer {other.json()['access_token']}"}
    other_token = client.post("/api/admin/events", headers=other_headers, json={"name": "Ortak etkinlik"}).json()["private_token"]
    client.post(f"/api/admin/events/{other_token}/members", headers=other_headers, json={"email": "admin@test.com", "role": "editor"})

    response = client.get("/api/admin/me/export", headers=admin_headers)
    assert response.status_code == 200
    assert response.headers["content-disposition"].startswith('attachment; filename="luma-event-verilerim-')
    assert "no-store" in response.headers["cache-control"]
    data = json.loads(response.content.decode("utf-8"))

    assert data["account"]["email"] == "admin@test.com"
    assert [c["email"] for c in data["contacts"]] == ["ayse@test.com"]
    [event] = data["events"]
    assert event["name"] == "Test Event"
    assert [(g["name"], g["dietary_requirements"]) for g in event["guests"]] == [("Zeynep", "Vejetaryen")]
    assert [m["message"] for m in event["guestbook_messages"]] == ["Çok güzeldi!"]
    assert [p["uploader_name"] for p in event["photos"]] == ["Zeynep"]
    assert data["team_memberships"] == [{"event_name": "Ortak etkinlik", "role": "editor", "created_at": data["team_memberships"][0]["created_at"]}]

    keys = set(_all_keys(data))
    assert not {k for k in keys if k.endswith("_hash") or "storage_key" in k or k.endswith("_id")}
    assert not keys & {"id", "password_hash", "private_token", "token_version"}
    assert TOKEN not in response.text
    # Someone else's event details are not part of this account's export.
    assert "other@test.com" not in json.dumps(data["events"])
