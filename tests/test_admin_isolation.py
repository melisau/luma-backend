TOKEN = "event-a-token-123456789012345678901234"


def _auth_headers(client, email, password):
    response = client.post("/api/admin/login", json={"email": email, "password": password})
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def test_admin_event_isolation(client, admin_headers):
    other = client.post(
        "/api/admin/register",
        json={"email": "diger@test.com", "password": "testpassword123", "display_name": "Diğer Admin"},
    )
    assert other.status_code == 201
    other_headers = _auth_headers(client, "diger@test.com", "testpassword123")

    create = client.post(
        "/api/admin/events",
        headers=other_headers,
        json={"name": "Diğer Admin Etkinliği", "venue": "Test", "city": "İstanbul"},
    )
    assert create.status_code == 201
    other_token = create.json()["private_token"]

    listed = client.get("/api/admin/events", headers=admin_headers)
    assert all(item["private_token"] != other_token for item in listed.json())

    other_list = client.get("/api/admin/events", headers=other_headers)
    assert len(other_list.json()) == 1
    assert other_list.json()[0]["private_token"] == other_token

    denied = client.get(f"/api/admin/events/{other_token}/guests", headers=admin_headers)
    assert denied.status_code == 404

    denied_patch = client.patch(
        f"/api/admin/events/{other_token}",
        headers=admin_headers,
        json={"name": "Ele geçirildi"},
    )
    assert denied_patch.status_code == 404


def test_new_user_starts_with_empty_event_list(client):
    register = client.post(
        "/api/admin/register",
        json={"email": "bos@test.com", "password": "testpassword123"},
    )
    assert register.status_code == 201
    headers = _auth_headers(client, "bos@test.com", "testpassword123")
    listed = client.get("/api/admin/events", headers=headers)
    assert listed.status_code == 200
    assert listed.json() == []
