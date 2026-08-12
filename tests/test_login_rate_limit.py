def test_login_rate_limit(client, monkeypatch):
    monkeypatch.setenv("LOGINS_PER_MINUTE", "3")
    from app.core.config import get_settings
    from app.services.rate_limit import login_rate_limiter

    get_settings.cache_clear()
    login_rate_limiter._events.clear()

    payload = {"email": "admin@test.com", "password": "wrong-password"}
    for _ in range(3):
        response = client.post("/api/admin/login", json=payload)
        assert response.status_code == 401

    blocked = client.post("/api/admin/login", json=payload)
    assert blocked.status_code == 429
