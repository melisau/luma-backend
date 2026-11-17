"""A1: legal pages and the required terms box at sign-up."""
from pathlib import Path

import pytest

ROOT = Path(__file__).parents[1]
FRONTEND = ROOT.parent / "luma-frontend"


def test_register_requires_accepting_terms(client):
    refused = client.post("/api/admin/register", json={"email": "yeni@test.com", "password": "testpassword123"})
    assert refused.status_code == 422
    assert "Kullanım Koşulları" in refused.json()["detail"]
    unticked = client.post("/api/admin/register",
                           json={"email": "yeni@test.com", "password": "testpassword123", "accept_terms": False})
    assert unticked.status_code == 422


def test_acceptance_time_and_version_are_stored(client):
    from app.core.config import get_settings
    from app.db import database
    from app.db.models import AdminUser
    response = client.post("/api/admin/register",
                           json={"email": "yeni@test.com", "password": "testpassword123", "accept_terms": True})
    assert response.status_code == 201
    with database.SessionLocal() as db:
        admin = db.query(AdminUser).filter(AdminUser.email == "yeni@test.com").one()
        assert admin.terms_accepted_at is not None
        assert admin.terms_version == get_settings().terms_version


def test_terms_migration_is_idempotent(tmp_path):
    import importlib.util
    import sqlalchemy as sa
    from alembic.migration import MigrationContext
    from alembic.operations import Operations
    path = ROOT / "alembic/versions/20261117_0024_terms_acceptance.py"
    spec = importlib.util.spec_from_file_location("terms_migration", path)
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)
    engine = sa.create_engine(f"sqlite:///{tmp_path / 'legacy.db'}")
    with engine.begin() as connection:
        connection.execute(sa.text("CREATE TABLE admin_users (id TEXT PRIMARY KEY, email TEXT)"))
        connection.execute(sa.text("INSERT INTO admin_users VALUES ('a1', 'eski@test.com')"))
        with Operations.context(MigrationContext.configure(connection)):
            migration.upgrade()
            migration.upgrade()
        row = connection.execute(sa.text("SELECT email, terms_accepted_at, terms_version FROM admin_users")).one()
        assert tuple(row) == ("eski@test.com", None, None)
    engine.dispose()


@pytest.mark.skipif(not (FRONTEND / "gizlilik.html").is_file(), reason="needs the luma-frontend checkout")
@pytest.mark.parametrize("slug", ["gizlilik", "aydinlatma", "kosullar"])
def test_legal_pages_are_served(tmp_path, monkeypatch, slug):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from app.main import mount_frontend
    app = FastAPI()
    mount_frontend(app, FRONTEND)
    response = TestClient(app).get(f"/{slug}")
    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]
    assert "kvkk@melisauyar.com" in response.text
