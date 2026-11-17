"""Two branches once both added a migration after the same parent; the app would refuse to start."""
from pathlib import Path


def test_migrations_have_a_single_head():
    from alembic.config import Config
    from alembic.script import ScriptDirectory
    root = Path(__file__).parents[1]
    config = Config(str(root / "alembic.ini"))
    config.set_main_option("script_location", str(root / "alembic"))
    assert len(ScriptDirectory.from_config(config).get_heads()) == 1
