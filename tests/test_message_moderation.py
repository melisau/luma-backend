TOKEN = "event-a-token-123456789012345678901234"


def test_new_message_starts_pending(client, admin_headers):
    create = client.post(
        f"/api/events/{TOKEN}/messages",
        json={"name": "Zeynep", "message": "Mutluluklar dilerim."},
    )
    assert create.status_code == 200
    assert create.json()["status"] == "pending"

    public = client.get(f"/api/events/{TOKEN}/messages")
    assert public.status_code == 200
    assert public.json() == []

    admin = client.get(f"/api/admin/events/{TOKEN}/messages", headers=admin_headers)
    assert any(item["message"] == "Mutluluklar dilerim." for item in admin.json())


def test_message_approve_flow(client, admin_headers):
    create = client.post(
        f"/api/events/{TOKEN}/messages",
        json={"name": "Can", "message": "Harika bir gün olsun."},
    )
    message_id = create.json()["id"]

    patch = client.patch(
        f"/api/admin/events/{TOKEN}/messages/{message_id}",
        headers=admin_headers,
        json={"status": "approved"},
    )
    assert patch.status_code == 200
    assert patch.json()["status"] == "approved"

    public = client.get(f"/api/events/{TOKEN}/messages")
    assert len(public.json()) == 1
    assert public.json()[0]["message"] == "Harika bir gün olsun."


def test_message_hide_excludes_public(client, admin_headers):
    create = client.post(
        f"/api/events/{TOKEN}/messages",
        json={"name": "Deniz", "message": "Gizlenecek mesaj."},
    )
    message_id = create.json()["id"]
    client.patch(
        f"/api/admin/events/{TOKEN}/messages/{message_id}",
        headers=admin_headers,
        json={"status": "approved"},
    )
    client.patch(
        f"/api/admin/events/{TOKEN}/messages/{message_id}",
        headers=admin_headers,
        json={"status": "hidden"},
    )

    public = client.get(f"/api/events/{TOKEN}/messages")
    assert public.json() == []
