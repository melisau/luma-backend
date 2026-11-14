"""The guest list is for the planner and their team only; invitees never see it."""

TOKEN = "event-a-token-123456789012345678901234"
GUEST = {"name": "Zeynep", "email": "zeynep@test.com", "group_name": "Gelin tarafı", "table_name": "Masa 3"}


def _add_guest(client, admin_headers):
    response = client.post(f"/api/admin/events/{TOKEN}/guests", headers=admin_headers, json=GUEST)
    assert response.status_code == 201


def test_invitee_with_the_link_cannot_list_guests(client, admin_headers):
    _add_guest(client, admin_headers)
    # Someone holding the invitation link but no planner login.
    assert client.get(f"/api/admin/events/{TOKEN}/guests").status_code == 401
    assert client.get(f"/api/admin/events/{TOKEN}/guests", headers={"X-Event-Token": TOKEN}).status_code == 401


def test_public_invitation_carries_no_guest_data(client, admin_headers):
    _add_guest(client, admin_headers)
    for path in (f"/api/events/{TOKEN}", f"/api/events/{TOKEN}/invitation", f"/api/events/{TOKEN}/messages", f"/api/events/{TOKEN}/photos"):
        response = client.get(path)
        assert response.status_code == 200, path
        for secret in ("zeynep@test.com", "Gelin tarafı", "Masa 3"):
            assert secret not in response.text, f"{secret!r} leaked in {path}"


def test_unrelated_account_cannot_list_guests(client, admin_headers):
    _add_guest(client, admin_headers)
    stranger = client.post("/api/admin/register", json={"email": "stranger@test.com", "password": "strangerpass123"})
    headers = {"Authorization": f"Bearer {stranger.json()['access_token']}"}
    assert client.get(f"/api/admin/events/{TOKEN}/guests", headers=headers).status_code == 404


def test_planner_and_team_can_list_guests(client, admin_headers):
    _add_guest(client, admin_headers)
    assert [g["email"] for g in client.get(f"/api/admin/events/{TOKEN}/guests", headers=admin_headers).json()] == ["zeynep@test.com"]

    helper = client.post("/api/admin/register", json={"email": "helper@test.com", "password": "helperpass1234"})
    helper_headers = {"Authorization": f"Bearer {helper.json()['access_token']}"}
    added = client.post(f"/api/admin/events/{TOKEN}/members", headers=admin_headers, json={"email": "helper@test.com", "role": "viewer"})
    assert added.status_code == 201
    assert [g["email"] for g in client.get(f"/api/admin/events/{TOKEN}/guests", headers=helper_headers).json()] == ["zeynep@test.com"]
