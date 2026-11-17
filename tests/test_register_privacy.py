"""B4: in production, sign-up does not reveal whether an e-mail address already has an account."""
import re

import pytest

from app.core.config import get_settings


@pytest.fixture()
def private_signup(client, monkeypatch):
    monkeypatch.setenv("REQUIRE_VERIFIED_EMAIL", "true")
    get_settings.cache_clear()
    from app.services import rate_limit
    rate_limit.register_rate_limiter._events.clear()
    rate_limit.login_rate_limiter._events.clear()
    sent = []
    import app.api.photos as photos
    monkeypatch.setattr(photos, "send_email", lambda to, subject, body: sent.append((to, subject, body)))
    yield sent
    get_settings.cache_clear()


def _register(client, email, password="testpassword123"):
    return client.post("/api/admin/register", json={"email": email, "password": password, "accept_terms": True})


def test_new_and_existing_addresses_get_the_same_answer(client, private_signup):
    new = _register(client, "yeni@test.com")
    existing = _register(client, "admin@test.com", password="something-else-1")
    assert new.status_code == existing.status_code == 202
    assert new.json() == existing.json()
    assert "access_token" not in new.json()
    assert new.headers.get("content-length") == existing.headers.get("content-length")


def test_each_address_gets_the_right_email(client, private_signup):
    _register(client, "yeni@test.com")
    _register(client, "admin@test.com", password="something-else-1")
    by_recipient = {to: (subject, body) for to, subject, body in private_signup}
    assert "/app.html?verify_token=" in by_recipient["yeni@test.com"][1]
    subject, body = by_recipient["admin@test.com"]
    assert "zaten hesabınız var" in subject
    assert "verify_token" not in body and "/app.html" in body


def test_existing_account_is_not_changed(client, private_signup):
    _register(client, "admin@test.com", password="something-else-1")
    assert client.post("/api/admin/login", json={"email": "admin@test.com", "password": "something-else-1"}).status_code == 401


def test_login_waits_for_verification(client, private_signup):
    _register(client, "yeni@test.com")
    wrong = client.post("/api/admin/login", json={"email": "yeni@test.com", "password": "wrong-password"})
    assert wrong.status_code == 401
    blocked = client.post("/api/admin/login", json={"email": "yeni@test.com", "password": "testpassword123", "accept_terms": True})
    assert blocked.status_code == 403
    assert "doğrulayın" in blocked.json()["detail"]
    token = re.search(r"verify_token=(\S+)", private_signup[-1][2]).group(1)
    assert client.post("/api/admin/email-verification/confirm", json={"token": token}).status_code == 200
    ok = client.post("/api/admin/login", json={"email": "yeni@test.com", "password": "testpassword123", "accept_terms": True})
    assert ok.status_code == 200 and ok.json()["access_token"]


def test_development_keeps_instant_sign_in(client, monkeypatch):
    monkeypatch.setenv("REQUIRE_VERIFIED_EMAIL", "false")
    get_settings.cache_clear()
    response = _register(client, "dev@test.com")
    assert response.status_code == 201 and response.json()["access_token"]
    assert _register(client, "dev@test.com").status_code == 409
    get_settings.cache_clear()
