"""A crowded wedding: ~200 guests on one venue Wi-Fi share a single IP."""
import pytest
from fastapi import HTTPException

from app.core.config import Settings, get_settings
from app.services import rate_limit


@pytest.fixture()
def limits(monkeypatch):
    monkeypatch.delenv("UPLOADS_PER_MINUTE", raising=False)
    monkeypatch.setenv("RATE_LIMIT_BACKEND", "memory")
    get_settings.cache_clear()
    rate_limit.upload_rate_limiter._events.clear()
    yield get_settings()
    rate_limit.upload_rate_limiter._events.clear()
    get_settings.cache_clear()


def test_defaults_carry_a_crowded_wedding(monkeypatch):
    for name in ("UPLOADS_PER_MINUTE", "EVENT_UPLOADS_PER_MINUTE"):
        monkeypatch.delenv(name, raising=False)
    settings = Settings(_env_file=None)
    # Old limits were 10 per IP and 20 per event.
    assert settings.uploads_per_minute >= 60
    assert settings.event_uploads_per_minute >= 150


def test_shared_wifi_burst_is_accepted(limits):
    # 60 guests behind the same IP each send one batch within the same minute.
    for _ in range(limits.uploads_per_minute):
        rate_limit.enforce_upload_rate_limit("203.0.113.7", "wedding")
    with pytest.raises(HTTPException) as blocked:
        rate_limit.enforce_upload_rate_limit("203.0.113.7", "wedding")
    assert blocked.value.status_code == 429
    retry = int(blocked.value.headers["Retry-After"])
    assert 1 <= retry <= 60
    assert "yeniden deneyin" in blocked.value.detail


def test_event_ceiling_spans_networks(limits):
    for index in range(limits.event_uploads_per_minute):
        rate_limit.enforce_upload_rate_limit(f"198.51.100.{index % 250}", "wedding")
    with pytest.raises(HTTPException):
        rate_limit.enforce_upload_rate_limit("192.0.2.1", "wedding")
    # Another event is unaffected.
    rate_limit.enforce_upload_rate_limit("192.0.2.1", "other-event")


def test_database_backend_sends_retry_after(client, monkeypatch):
    monkeypatch.setenv("RATE_LIMIT_BACKEND", "database")
    get_settings.cache_clear()
    limiter = rate_limit.RateLimiter()
    limiter.check("upload-db-test", 2)
    limiter.check("upload-db-test", 2)
    with pytest.raises(HTTPException) as blocked:
        limiter.check("upload-db-test", 2)
    assert blocked.value.status_code == 429
    assert 1 <= int(blocked.value.headers["Retry-After"]) <= 60
    get_settings.cache_clear()


def test_upload_endpoint_returns_retry_after(client, monkeypatch):
    monkeypatch.setenv("UPLOADS_PER_MINUTE", "1")
    get_settings.cache_clear()
    rate_limit.upload_rate_limiter._events.clear()
    url = "/api/events/event-a-token-123456789012345678901234/photos"
    files = {"files": ("a.txt", b"not an image", "text/plain")}
    client.post(url, data={"uploader_name": "Ada"}, files=files)
    blocked = client.post(url, data={"uploader_name": "Ada"}, files=files)
    assert blocked.status_code == 429
    assert blocked.headers["retry-after"].isdigit()
    rate_limit.upload_rate_limiter._events.clear()
    get_settings.cache_clear()
