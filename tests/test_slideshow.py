"""Slide show: owner-curated, approved photos only (guest uploads appear after approval)."""
import io

from PIL import Image

TOKEN = "event-a-token-123456789012345678901234"


def _jpeg(color):
    buffer = io.BytesIO()
    Image.new("RGB", (64, 48), color).save(buffer, "JPEG")
    return buffer.getvalue()


def _upload(client, color, name="Misafir"):
    response = client.post(f"/api/events/{TOKEN}/photos", data={"uploader_name": name, "caption": f"{color} an"},
                           files={"files": (f"{color}.jpg", _jpeg(color), "image/jpeg")})
    assert response.status_code == 200, response.text
    return response.json()["uploaded"][0]["id"]


def _approve(client, admin_headers, photo_id, value="approved"):
    assert client.patch(f"/api/admin/photos/{photo_id}", headers=admin_headers, json={"status": value}).status_code == 200


def _admin(client, admin_headers):
    return client.get(f"/api/admin/events/{TOKEN}/slideshow", headers=admin_headers).json()


def _ids(items):
    return [item["id"] for item in items]


def test_guest_uploads_join_only_after_approval(client, admin_headers):
    first = _upload(client, "red")
    second = _upload(client, "blue")
    data = _admin(client, admin_headers)
    assert data["slides"] == []
    assert data["available"] == []
    _approve(client, admin_headers, first)
    assert _ids(_admin(client, admin_headers)["slides"]) == [first]
    _approve(client, admin_headers, second, "hidden")
    assert _ids(_admin(client, admin_headers)["slides"]) == [first]


def test_owner_orders_removes_and_new_approvals_follow(client, admin_headers):
    a, b, c = (_upload(client, color) for color in ("red", "green", "blue"))
    for photo in (a, b):
        _approve(client, admin_headers, photo)
    saved = client.put(f"/api/admin/events/{TOKEN}/slideshow", headers=admin_headers,
                       json={"photo_ids": [b, "not-a-photo", c], "transition": "zoom", "seconds": 8, "title": "Elif & Deniz"}).json()
    # c is not approved yet, so it cannot be placed; a was left out, so it is removed.
    assert _ids(saved["slides"]) == [b]
    assert _ids(saved["available"]) == [a]
    assert (saved["transition"], saved["seconds"], saved["title"]) == ("zoom", 8, "Elif & Deniz")
    _approve(client, admin_headers, c)
    assert _ids(_admin(client, admin_headers)["slides"]) == [b, c]  # auto_add brings later approvals
    client.put(f"/api/admin/events/{TOKEN}/slideshow", headers=admin_headers, json={"auto_add": False})
    d = _upload(client, "yellow")
    _approve(client, admin_headers, d)
    assert _ids(_admin(client, admin_headers)["slides"]) == [b, c]
    assert set(_ids(_admin(client, admin_headers)["available"])) == {a, d}


def test_settings_are_validated(client, admin_headers):
    url = f"/api/admin/events/{TOKEN}/slideshow"
    assert client.put(url, headers=admin_headers, json={"transition": "spin"}).status_code == 422
    assert client.put(url, headers=admin_headers, json={"seconds": 1}).status_code == 422
    assert client.put(url, json={"seconds": 5}).status_code == 401


def test_player_feed_for_guests_and_owner_screen(client, admin_headers):
    photo = _upload(client, "red", name="Ayşe")
    _approve(client, admin_headers, photo)
    feed = client.get(f"/api/events/{TOKEN}/slideshow").json()
    assert [s["id"] for s in feed["slides"]] == [photo]
    assert feed["slides"][0]["uploader_name"] == "Ayşe"
    assert feed["title"] == "Test Event" and feed["transition"] == "fade"
    client.put(f"/api/admin/events/{TOKEN}/slideshow", headers=admin_headers, json={"show_captions": False, "show_to_guests": False})
    assert client.get(f"/api/events/{TOKEN}/slideshow").status_code == 404
    client.post(f"/api/admin/events/{TOKEN}/access-preview", headers=admin_headers)
    owner_feed = client.get(f"/api/events/{TOKEN}/slideshow").json()
    assert owner_feed["slides"][0]["uploader_name"] == ""


def test_private_album_keeps_the_show_on_the_owners_screen(client, admin_headers):
    shown = _upload(client, "red")
    kept_out = _upload(client, "blue")
    for photo in (shown, kept_out):
        _approve(client, admin_headers, photo)
    client.put(f"/api/admin/events/{TOKEN}/slideshow", headers=admin_headers, json={"photo_ids": [shown]})
    client.patch(f"/api/admin/events/{TOKEN}", headers=admin_headers, json={"album_public": False})
    # "Share approved photos with guests" is off: guests see neither the show nor its photos.
    assert client.get(f"/api/events/{TOKEN}/slideshow").status_code == 404
    assert client.get(f"/api/photos/{shown}?access={TOKEN}").status_code == 404
    assert _admin(client, admin_headers)["album_public"] is False
    # The owner's screen (panel preview) still plays it, but only the photos in the show.
    client.post(f"/api/admin/events/{TOKEN}/access-preview", headers=admin_headers)
    assert [s["id"] for s in client.get(f"/api/events/{TOKEN}/slideshow").json()["slides"]] == [shown]
    assert client.get(f"/api/photos/{shown}?access={TOKEN}").status_code == 200
    assert client.get(f"/api/photos/{shown}/thumbnail?access={TOKEN}").status_code == 200
    assert client.get(f"/api/photos/{kept_out}?access={TOKEN}").status_code == 404


def test_slideshow_migration_is_idempotent(tmp_path):
    import importlib.util
    from pathlib import Path
    import sqlalchemy as sa
    from alembic.migration import MigrationContext
    from alembic.operations import Operations
    path = Path(__file__).parents[1] / "alembic/versions/20261117_0026_slideshow.py"
    spec = importlib.util.spec_from_file_location("slideshow_migration", path)
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)
    engine = sa.create_engine(f"sqlite:///{tmp_path / 'legacy.db'}")
    with engine.begin() as connection:
        connection.execute(sa.text("CREATE TABLE events (id TEXT PRIMARY KEY)"))
        connection.execute(sa.text("INSERT INTO events VALUES ('e1')"))
        with Operations.context(MigrationContext.configure(connection)):
            migration.upgrade()
            migration.upgrade()
        assert connection.execute(sa.text("SELECT slideshow FROM events")).scalar_one() == "{}"
    engine.dispose()


def test_migrations_have_a_single_head():
    from pathlib import Path
    from alembic.config import Config
    from alembic.script import ScriptDirectory
    root = Path(__file__).parents[1]
    config = Config(str(root / "alembic.ini"))
    config.set_main_option("script_location", str(root / "alembic"))
    assert len(ScriptDirectory.from_config(config).get_heads()) == 1
