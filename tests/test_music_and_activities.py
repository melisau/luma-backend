TOKEN = "event-a-token-123456789012345678901234"


def test_music_upload_and_stream(client, admin_headers):
    upload = client.post(
        f"/api/admin/events/{TOKEN}/invitation/music",
        headers=admin_headers,
        files={"file": ("song.mp3", b"fake-mp3-content", "audio/mpeg")},
    )
    assert upload.status_code == 200
    body = upload.json()
    assert body["music_url"] == f"/api/events/{TOKEN}/music"
    assert body["music_filename"] == "song.mp3"

    invitation = client.get(f"/api/events/{TOKEN}/invitation")
    assert invitation.status_code == 200
    assert invitation.json()["music_url"] == f"/api/events/{TOKEN}/music"

    stream = client.get(f"/api/events/{TOKEN}/music")
    assert stream.status_code == 200
    assert stream.content == b"fake-mp3-content"
    assert "audio" in stream.headers["content-type"]

    delete = client.delete(
        f"/api/admin/events/{TOKEN}/invitation/music",
        headers=admin_headers,
    )
    assert delete.status_code == 200
    assert delete.json()["music_url"] is None


def test_activities_recorded_for_guest_and_rsvp(client, admin_headers):
    guest = client.post(
        f"/api/admin/events/{TOKEN}/guests",
        headers=admin_headers,
        json={
            "name": "Can Yilmaz",
            "email": "can@example.com",
            "status": "pending",
            "people": 1,
            "source": "admin",
        },
    )
    assert guest.status_code == 201

    listed = client.get(f"/api/admin/events/{TOKEN}/activities", headers=admin_headers)
    assert listed.status_code == 200
    texts = [item["text"] for item in listed.json()]
    assert any("Can Yilmaz" in text for text in texts)

    client.post(
        f"/api/events/{TOKEN}/rsvp",
        json={
            "name": "Deniz Kaya",
            "email": "deniz@example.com",
            "status": "attending",
            "people": 2,
        },
    )
    listed = client.get(f"/api/admin/events/{TOKEN}/activities", headers=admin_headers)
    texts = [item["text"] for item in listed.json()]
    assert any("Deniz Kaya" in text for text in texts)


def test_admin_can_create_activity(client, admin_headers):
    response = client.post(
        f"/api/admin/events/{TOKEN}/activities",
        headers=admin_headers,
        json={"text": "Manuel test kaydı", "kind": "check"},
    )
    assert response.status_code == 201
    assert response.json()["text"] == "Manuel test kaydı"
