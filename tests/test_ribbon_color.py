TOKEN = "event-a-token-123456789012345678901234"

def test_ribbon_color_persists_and_rejects_invalid_values(client, admin_headers):
    url = f"/api/admin/events/{TOKEN}/invitation"
    response = client.patch(url, headers=admin_headers, json={"ribbon_color": "#992244"})
    assert response.status_code == 200
    assert response.json()["ribbon_color"] == "#992244"
    client.patch(url, headers=admin_headers, json={"tagline": "Celebration"})
    assert client.get(f"/api/events/{TOKEN}/invitation").json()["ribbon_color"] == "#992244"
    assert client.patch(url, headers=admin_headers, json={"ribbon_color": "invalid"}).status_code == 422
