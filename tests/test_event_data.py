TOKEN = "event-a-token-123456789012345678901234"


def test_public_rsvp_creates_guest(client):
    response = client.post(
        f"/api/events/{TOKEN}/rsvp",
        json={
            "name": "Ayşe Yılmaz",
            "email": "ayse@example.com",
            "status": "attending",
            "people": 2,
        },
    )
    assert response.status_code == 200
    assert response.json()["email"] == "ayse@example.com"
    assert response.json()["source"] == "external"


def test_admin_lists_guests_after_rsvp(client, admin_headers):
    client.post(
        f"/api/events/{TOKEN}/rsvp",
        json={"name": "Mehmet", "email": "mehmet@example.com", "status": "pending", "people": 1},
    )
    response = client.get(f"/api/admin/events/{TOKEN}/guests", headers=admin_headers)
    assert response.status_code == 200
    emails = {item["email"] for item in response.json()}
    assert "mehmet@example.com" in emails


def test_guestbook_message_flow(client, admin_headers):
    create = client.post(
        f"/api/events/{TOKEN}/messages",
        json={"name": "Zeynep", "message": "Mutluluklar dilerim."},
    )
    assert create.status_code == 200
    listed = client.get(f"/api/admin/events/{TOKEN}/messages", headers=admin_headers)
    assert listed.status_code == 200
    assert any(item["message"] == "Mutluluklar dilerim." for item in listed.json())


def test_invitation_patch_and_read(client, admin_headers):
    patch = client.patch(
        f"/api/admin/events/{TOKEN}/invitation",
        headers=admin_headers,
        json={"tagline": "Yeni tagline", "venue": "Yeni Mekan", "city": "Ankara"},
    )
    assert patch.status_code == 200
    assert patch.json()["tagline"] == "Yeni tagline"
    public = client.get(f"/api/events/{TOKEN}/invitation")
    assert public.status_code == 200
    assert public.json()["venue"] == "Yeni Mekan"


def test_admin_create_and_delete_guest(client, admin_headers):
    create = client.post(
        f"/api/admin/events/{TOKEN}/guests",
        headers=admin_headers,
        json={"name": "Ali", "email": "ali@example.com", "status": "pending", "people": 1},
    )
    assert create.status_code == 201
    guest_id = create.json()["id"]
    delete = client.delete(f"/api/admin/events/{TOKEN}/guests/{guest_id}", headers=admin_headers)
    assert delete.status_code == 204
