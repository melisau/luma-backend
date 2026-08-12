def test_admin_register_and_login(client):
    register = client.post(
        "/api/admin/register",
        json={
            "email": "yeni@test.com",
            "password": "testpassword123",
            "display_name": "Yeni Kullanıcı",
        },
    )
    assert register.status_code == 201
    body = register.json()
    assert body["email"] == "yeni@test.com"
    assert body["display_name"] == "Yeni Kullanıcı"
    assert body["access_token"]

    login = client.post(
        "/api/admin/login",
        json={"email": "yeni@test.com", "password": "testpassword123"},
    )
    assert login.status_code == 200
    assert login.json()["email"] == "yeni@test.com"


def test_admin_register_duplicate_email(client):
    first = client.post(
        "/api/admin/register",
        json={"email": "dup@test.com", "password": "testpassword123"},
    )
    assert first.status_code == 201

    second = client.post(
        "/api/admin/register",
        json={"email": "dup@test.com", "password": "testpassword123"},
    )
    assert second.status_code == 409
    assert "kayıtlı" in second.json()["detail"].lower()


def test_admin_register_short_password(client):
    response = client.post(
        "/api/admin/register",
        json={"email": "short@test.com", "password": "1234567"},
    )
    assert response.status_code == 422
