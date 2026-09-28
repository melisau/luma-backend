TOKEN = "event-a-token-123456789012345678901234"

def test_paper_and_exhibition_settings_roundtrip(client, admin_headers):
    url = f"/api/admin/events/{TOKEN}/invitation"
    public_url = f"/api/events/{TOKEN}/invitation"
    assert client.get(public_url).json()["presentation"]["paper_style"] == "none"
    presentation = {"opening_hand": "witch", "button_radius": 16, "paper_style": "ticket", "paper_texture": "floral", "paper_target": "all", "paper_color": "#F8F5EF", "paper_text": "#25463B", "photo_layout": "asymmetric", "photo_columns": 4, "section_transition": "torn", "transition_target": "hero", "transition_color": "#F5F0E6", "opening_background_color": "#B97978"}
    assert client.patch(url, headers=admin_headers, json={"presentation": presentation}).status_code == 200
    assert client.patch(url, headers=admin_headers, json={"tagline": "Celebration"}).status_code == 200
    assert client.get(public_url).json()["presentation"] == presentation
    for invalid in ({"opening_hand": "unknown"}, {"button_radius": -1}, {"button_radius": 1000}, {"opening_background_color": "red"}, {"section_transition": "script"}, {"transition_color": "red"}, {"paper_style": "script"}, {"paper_color": "red"}, {"photo_layout": "unknown"}, {"photo_columns": 12}):
        assert client.patch(url, headers=admin_headers, json={"presentation": invalid}).status_code == 422
    assert client.patch(url, headers=admin_headers, json={"presentation": {"paper_style": "none", "photo_layout": "stacked"}}).status_code == 200
    assert client.get(public_url).json()["presentation"]["paper_style"] == "none"


def test_presentation_migration_preserves_existing_event(tmp_path):
    import importlib.util
    from pathlib import Path
    import sqlalchemy as sa
    from alembic.migration import MigrationContext
    from alembic.operations import Operations
    engine = sa.create_engine(f"sqlite:///{tmp_path / 'legacy.db'}")
    with engine.begin() as connection:
        connection.execute(sa.text("CREATE TABLE events (id TEXT PRIMARY KEY, name TEXT)"))
        connection.execute(sa.text("INSERT INTO events VALUES ('existing', 'Birthday')"))
        path = Path(__file__).parents[1] / "alembic/versions/20260928_0021_presentation.py"
        spec = importlib.util.spec_from_file_location("presentation_migration", path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        with Operations.context(MigrationContext.configure(connection)):
            module.upgrade()
            module.upgrade()
        assert connection.execute(sa.text("SELECT name,presentation FROM events")).one() == ("Birthday", "{}")
    engine.dispose()
