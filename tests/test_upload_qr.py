def test_upload_qr_is_unique_per_event(client, admin_headers):
    first = client.post(
        "/api/admin/events",
        headers=admin_headers,
        json={"name": "Düğün A", "slug": "dugun-a"},
    )
    second = client.post(
        "/api/admin/events",
        headers=admin_headers,
        json={"name": "Düğün B", "slug": "dugun-b"},
    )
    assert first.status_code == 201
    assert second.status_code == 201

    token_a = first.json()["private_token"]
    token_b = second.json()["private_token"]
    assert token_a != token_b

    qr_a = client.get(f"/api/events/{token_a}/upload-qr")
    qr_b = client.get(f"/api/events/{token_b}/upload-qr")
    assert qr_a.status_code == 200
    assert qr_b.status_code == 200
    assert qr_a.content != qr_b.content

    assert f'/e/{token_a}/upload' != f'/e/{token_b}/upload'
    assert 'dugun-a' in qr_a.headers["content-disposition"]
    assert 'dugun-b' in qr_b.headers["content-disposition"]


def test_upload_qr_uses_event_private_token_not_path_alias(client, admin_headers):
    created = client.post(
        "/api/admin/events",
        headers=admin_headers,
        json={"name": "Nişan", "slug": "nisan-2026"},
    )
    token = created.json()["private_token"]

    response = client.get(f"/api/events/{token}/upload-qr?download=1")
    assert response.status_code == 200
    assert response.headers["content-type"] == "image/png"
    assert "nisan-2026" in response.headers["content-disposition"]
