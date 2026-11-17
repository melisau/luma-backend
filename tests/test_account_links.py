"""E-mailed verification and reset links must open app.html, which handles them."""
import re

import pytest


@pytest.fixture()
def outbox(monkeypatch):
    sent = []
    import app.api.photos as photos
    monkeypatch.setattr(photos, "send_email", lambda to, subject, body: sent.append((to, subject, body)))
    return sent


def _link(body):
    return re.search(r"https?://\S+", body).group(0)


def test_verification_link_opens_the_app(client, outbox):
    response = client.post("/api/admin/register", json={"email": "yeni@test.com", "password": "testpassword123", "accept_terms": True})
    assert response.status_code == 201
    link = _link(outbox[-1][2])
    assert "/app.html?verify_token=" in link
    token = link.split("verify_token=")[1]
    assert client.post("/api/admin/email-verification/confirm", json={"token": token}).status_code == 200


def test_reset_link_opens_the_app(client, outbox):
    client.post("/api/admin/password-reset/request", json={"email": "admin@test.com"})
    link = _link(outbox[-1][2])
    assert "/app.html?reset_token=" in link
