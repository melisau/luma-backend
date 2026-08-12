from collections.abc import Generator

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.core.config import ROOT, get_settings

settings = get_settings()
connect_args = {"check_same_thread": False} if settings.database_url.startswith("sqlite") else {}
engine = create_engine(settings.database_url, connect_args=connect_args)
SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)


class Base(DeclarativeBase):
    pass


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


EVENT_COLUMN_MIGRATIONS: dict[str, str] = {
    "event_date": "DATETIME",
    "venue": "VARCHAR(255) DEFAULT ''",
    "city": "VARCHAR(255) DEFAULT ''",
    "tagline": "VARCHAR(512) DEFAULT ''",
    "story_title": "VARCHAR(512) DEFAULT ''",
    "story_text": "TEXT DEFAULT ''",
    "guest_note": "TEXT DEFAULT ''",
    "cover_storage_key": "TEXT",
    "music_storage_key": "TEXT",
    "music_filename": "VARCHAR(512)",
    "music_mime_type": "VARCHAR(128)",
}


def migrate_db() -> None:
    inspector = inspect(engine)
    with engine.begin() as connection:
        if inspector.has_table("admin_users"):
            admin_columns = {column["name"] for column in inspector.get_columns("admin_users")}
            if "display_name" not in admin_columns:
                connection.execute(text("ALTER TABLE admin_users ADD COLUMN display_name VARCHAR(255)"))

        if not inspector.has_table("events"):
            return
        existing = {column["name"] for column in inspector.get_columns("events")}
        for name, ddl in EVENT_COLUMN_MIGRATIONS.items():
            if name not in existing:
                connection.execute(text(f"ALTER TABLE events ADD COLUMN {name} {ddl}"))

        if inspector.has_table("guestbook_messages"):
            message_columns = {column["name"] for column in inspector.get_columns("guestbook_messages")}
            if "status" not in message_columns:
                connection.execute(
                    text(
                        "ALTER TABLE guestbook_messages ADD COLUMN status VARCHAR(32) NOT NULL DEFAULT 'approved'"
                    )
                )


def run_alembic_migrations() -> None:
    try:
        from alembic import command
        from alembic.config import Config

        alembic_cfg = Config(str(ROOT / "alembic.ini"))
        alembic_cfg.set_main_option("script_location", str(ROOT / "alembic"))
        alembic_cfg.set_main_option("sqlalchemy.url", settings.database_url)
        command.upgrade(alembic_cfg, "head")
    except Exception:
        migrate_db()


def init_db() -> None:
    from app.db import models  # noqa: F401

    Base.metadata.create_all(bind=engine)
    run_alembic_migrations()
