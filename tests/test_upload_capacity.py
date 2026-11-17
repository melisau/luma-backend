"""A crowded wedding must not freeze the site while photos are processed."""
import asyncio
import threading

from app.core.config import Settings, get_settings

TOKEN = "event-a-token-123456789012345678901234"


def test_upload_endpoints_run_off_the_event_loop():
    # Pillow work must not run on the event loop, or every other request stalls.
    import inspect
    from app.api import event_data, photos
    for endpoint in (event_data.admin_upload_cover, event_data.admin_upload_music, event_data.admin_upload_memory_cover):
        assert not asyncio.iscoroutinefunction(endpoint), endpoint.__name__
    guest = inspect.getsource(photos.upload_event_photos)
    assert "await run_in_threadpool(photos.upload_photos" in guest
    assert "await run_in_threadpool(enforce_upload_rate_limit" in guest
    # Waiting for a processing slot must not hold a threadpool token.
    assert "await _take_processing_slot(" in guest


def test_event_photo_cap_fits_a_big_wedding(monkeypatch):
    monkeypatch.delenv("MAX_PHOTOS_PER_EVENT", raising=False)
    settings = Settings(_env_file=None)
    assert settings.max_photos_per_event >= 3000
    assert 1 <= settings.photo_processing_concurrency <= 4


def test_busy_processing_answers_503_with_retry_after(client, monkeypatch):
    from app.api import photos
    monkeypatch.setenv("PHOTO_PROCESSING_WAIT_SECONDS", "0")
    get_settings.cache_clear()
    slots = threading.BoundedSemaphore(1)
    slots.acquire()  # every slot already in use
    monkeypatch.setattr(photos, "_processing_slots", slots)
    response = client.post(f"/api/events/{TOKEN}/photos", data={"uploader_name": "Ada"},
                           files={"files": ("a.jpg", b"x", "image/jpeg")})
    assert response.status_code == 503
    assert response.headers["retry-after"] == "5"
    slots.release()
    get_settings.cache_clear()


def test_slot_is_released_after_a_failed_upload(client, monkeypatch):
    from app.api import photos
    slots = threading.BoundedSemaphore(1)
    monkeypatch.setattr(photos, "_processing_slots", slots)
    bad = client.post(f"/api/events/{TOKEN}/photos", data={"uploader_name": "Ada"},
                      files={"files": ("a.txt", b"not an image", "text/plain")})
    assert bad.status_code >= 400
    assert slots.acquire(timeout=0)  # free again
    slots.release()


def test_waiting_upload_gives_its_database_connection_back():
    import inspect
    from app.api import photos
    source = inspect.getsource(photos.upload_event_photos)
    first_await = source.index("await ")
    assert source.index("db.close()") < first_await


def test_postgres_pool_has_room_for_a_crowd():
    source = (__import__("pathlib").Path(__file__).parents[1] / "app/db/database.py").read_text(encoding="utf-8")
    assert '"pool_size": 20' in source and '"max_overflow": 30' in source and '"pool_pre_ping": True' in source


def test_startup_migrations_keep_app_loggers_enabled(tmp_path, monkeypatch):
    import logging
    from app.db import database
    logger = logging.getLogger("app.api.photos")
    assert not logger.disabled
    engine = database.create_engine(f"sqlite:///{tmp_path / 'logs.db'}")
    monkeypatch.setattr(database, "engine", engine)
    database.Base.metadata.create_all(bind=engine)
    database.run_alembic_migrations()
    assert not logger.disabled
    assert not logging.getLogger("app.services.email_service").disabled


def test_access_check_releases_its_connection(client):
    # The check runs while the request body (a photo over slow Wi-Fi) may still be arriving.
    from app.db import database
    pool = database.engine.pool
    before = pool.checkedout()
    response = client.get(f"/api/events/{TOKEN}/invitation")
    assert response.status_code == 200
    assert pool.checkedout() <= before

    from app.api import event_access
    from starlette.requests import Request
    session = database.SessionLocal()
    scope = {"type": "http", "path": f"/api/events/{TOKEN}/photos", "path_params": {"event_token": TOKEN},
             "headers": [], "method": "POST", "query_string": b""}
    event_access.require_event_access(Request(scope), session)
    assert not session.in_transaction()
    session.close()
