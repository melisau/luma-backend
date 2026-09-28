import pytest
TOKEN = "event-a-token-123456789012345678901234"

def test_palette_persists_public_and_resets(client, admin_headers):
    url = f"/api/admin/events/{TOKEN}/invitation"
    palette = {"background": "#152631", "text": "#ffffff", "badge_background": "#ffaa55", "badge_text": "#112233"}
    saved = client.patch(url, headers=admin_headers, json={"palette": palette})
    assert saved.status_code == 200
    assert saved.json()["palette"] == palette
    assert client.get(f"/api/events/{TOKEN}/invitation").json()["palette"] == palette
    client.patch(url, headers=admin_headers, json={"tagline": "A new day"})
    assert client.get(f"/api/events/{TOKEN}/invitation").json()["palette"] == palette
    assert client.patch(url, headers=admin_headers, json={"palette": {}}).json()["palette"] == {}

@pytest.mark.parametrize("palette", [{"text": "red"}, {"text": "url(evil)"}, {"unknown": "#ffffff"}, {"text": None}])
def test_invalid_palette_rejected(client, admin_headers, palette):
    assert client.patch(f"/api/admin/events/{TOKEN}/invitation", headers=admin_headers, json={"palette": palette}).status_code == 422


def test_existing_event_survives_palette_migration():
    from alembic import command
    from alembic.config import Config
    from sqlalchemy import create_engine, text
    engine = create_engine("sqlite://")
    with engine.begin() as connection:
        connection.execute(text("CREATE TABLE events (id TEXT PRIMARY KEY, name TEXT NOT NULL)"))
        connection.execute(text("INSERT INTO events (id, name) VALUES ('kept', 'Existing event')"))
        config = Config("alembic.ini")
        config.attributes["connection"] = connection
        command.stamp(config, "20260912_0017")
        command.upgrade(config, "head")
        row = connection.execute(text("SELECT name, palette FROM events WHERE id='kept'" )).one()
        assert tuple(row) == ("Existing event", "{}")
    engine.dispose()
