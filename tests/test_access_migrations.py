import importlib.util
from pathlib import Path
import sqlalchemy as sa
from alembic.migration import MigrationContext
from alembic.operations import Operations


def test_access_migrations_preserve_legacy_data(tmp_path):
    engine=sa.create_engine(f'sqlite:///{tmp_path / "legacy.db"}')
    with engine.begin() as connection:
        connection.execute(sa.text('CREATE TABLE guests (id TEXT PRIMARY KEY, email TEXT)'))
        connection.execute(sa.text("INSERT INTO guests VALUES ('guest', 'legacy@example.com')"))
        connection.execute(sa.text('CREATE TABLE photos (id TEXT PRIMARY KEY, event_id TEXT)'))
        connection.execute(sa.text("INSERT INTO photos VALUES ('photo1', 'event'), ('photo2', 'event')"))
        for filename in ['20260912_0009_rsvp_access.py','20260912_0010_photo_dedup.py']:
            spec=importlib.util.spec_from_file_location('migration',Path(__file__).parents[1]/'alembic/versions'/filename)
            module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
            with Operations.context(MigrationContext.configure(connection)):
                module.upgrade();module.upgrade()
        assert connection.execute(sa.text('SELECT email,rsvp_token_hash FROM guests')).one()==('legacy@example.com',None)
        assert connection.execute(sa.text('SELECT count(*) FROM photos WHERE content_hash IS NULL')).scalar()==2
    engine.dispose()
