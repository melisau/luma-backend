import os
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import sessionmaker

os.environ.setdefault("SECRET_KEY", "test-secret-key")
os.environ.setdefault("ADMIN_EMAIL", "admin@test.com")
os.environ.setdefault("ADMIN_PASSWORD", "testpassword123")
os.environ.setdefault("SEED_EVENT_TOKEN", "event-a-token-123456789012345678901234")
os.environ.setdefault("UPLOADS_PER_MINUTE", "100")
os.environ.setdefault("SERVE_FRONTEND", "false")
os.environ.setdefault("STORAGE_BACKEND", "local")

from app.core.config import get_settings
from app.core.security import hash_password
from app.db import database as db_module
from app.db.database import init_db
from app.db.models import AdminUser, Event
from app.main import app


def rebind_database(db_url: str) -> None:
    connect_args = {"check_same_thread": False} if db_url.startswith("sqlite") else {}
    engine = db_module.create_engine(db_url, connect_args=connect_args)
    db_module.engine = engine
    db_module.SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)
    init_db()


@pytest.fixture()
def client(tmp_path, monkeypatch):
    db_path = tmp_path / "test.db"
    uploads = tmp_path / "uploads"
    uploads.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{db_path}")
    monkeypatch.setenv("LOCAL_STORAGE_PATH", str(uploads))
    get_settings.cache_clear()
    rebind_database(f"sqlite:///{db_path}")

    db = db_module.SessionLocal()
    try:
        settings = get_settings()
        admin = db.query(AdminUser).filter(AdminUser.email == settings.admin_email.lower()).one_or_none()
        if not admin:
            admin = AdminUser(
                email=settings.admin_email.lower(),
                password_hash=hash_password(settings.admin_password),
            )
            db.add(admin)
            db.flush()
        if not db.query(Event).filter(Event.private_token == "event-a-token-123456789012345678901234").first():
            db.add(
                Event(
                    admin_id=admin.id,
                    name="Test Event",
                    slug="test-event",
                    private_token="event-a-token-123456789012345678901234",
                )
            )
            db.commit()
    finally:
        db.close()

    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture(autouse=True)
def reset_rate_limiters():
    from app.services.rate_limit import login_rate_limiter, message_rate_limiter, upload_rate_limiter

    login_rate_limiter._events.clear()
    message_rate_limiter._events.clear()
    upload_rate_limiter._events.clear()
    yield
    login_rate_limiter._events.clear()
    message_rate_limiter._events.clear()
    upload_rate_limiter._events.clear()


@pytest.fixture()
def admin_headers(client):
    response = client.post(
        "/api/admin/login",
        json={"email": "admin@test.com", "password": "testpassword123"},
    )
    token = response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}
