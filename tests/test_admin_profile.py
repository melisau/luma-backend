def test_admin_profile_update(client, admin_headers):
    me = client.get("/api/admin/me", headers=admin_headers)
    assert me.status_code == 200
    assert me.json()["email"] == "admin@test.com"

    patch = client.patch(
        "/api/admin/me",
        headers=admin_headers,
        json={"display_name": "Melisa"},
    )
    assert patch.status_code == 200
    assert patch.json()["display_name"] == "Melisa"

    login = client.post(
        "/api/admin/login",
        json={"email": "admin@test.com", "password": "testpassword123"},
    )
    assert login.status_code == 200
    assert login.json()["display_name"] == "Melisa"
