TOKEN = "event-a-token-123456789012345678901234"


def test_admin_create_event(client, admin_headers):
    response = client.post(
        "/api/admin/events",
        headers=admin_headers,
        json={
            "name": "Yeni Düğün",
            "event_date": "2026-10-01T18:00:00+00:00",
            "venue": "Boğaz Yalısı",
            "city": "İstanbul",
        },
    )
    assert response.status_code == 201
    body = response.json()
    assert body["name"] == "Yeni Düğün"
    assert body["private_token"]
    assert body["slug"]


def test_admin_update_event(client, admin_headers):
    patch = client.patch(
        f"/api/admin/events/{TOKEN}",
        headers=admin_headers,
        json={"name": "Güncellenmiş Etkinlik", "uploads_enabled": False},
    )
    assert patch.status_code == 200
    assert patch.json()["name"] == "Güncellenmiş Etkinlik"
    assert patch.json()["uploads_enabled"] is False


def test_admin_change_password(client, admin_headers):
    response = client.post(
        "/api/admin/change-password",
        headers=admin_headers,
        json={"current_password": "testpassword123", "new_password": "newpassword456"},
    )
    assert response.status_code == 204
    login_old = client.post(
        "/api/admin/login",
        json={"email": "admin@test.com", "password": "testpassword123"},
    )
    assert login_old.status_code == 401
    login_new = client.post(
        "/api/admin/login",
        json={"email": "admin@test.com", "password": "newpassword456"},
    )
    assert login_new.status_code == 200


def test_admin_delete_event(client, admin_headers):
    create = client.post(
        "/api/admin/events",
        headers=admin_headers,
        json={"name": "Silinecek Etkinlik", "venue": "Test", "city": "İstanbul"},
    )
    assert create.status_code == 201
    token = create.json()["private_token"]

    delete = client.delete(f"/api/admin/events/{token}", headers=admin_headers)
    assert delete.status_code == 204

    missing = client.get(f"/api/events/{token}")
    assert missing.status_code == 404

    listed = client.get("/api/admin/events", headers=admin_headers)
    assert all(item["private_token"] != token for item in listed.json())


def test_admin_delete_event_not_found(client, admin_headers):
    response = client.delete("/api/admin/events/nonexistent-token", headers=admin_headers)
    assert response.status_code == 404
