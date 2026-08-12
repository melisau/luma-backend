"""music columns and event activities table

Revision ID: 20260812_0001
Revises:
Create Date: 2026-08-12

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

revision: str = "20260812_0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)

    if inspector.has_table("events"):
        existing = {column["name"] for column in inspector.get_columns("events")}
        if "music_storage_key" not in existing:
            op.add_column("events", sa.Column("music_storage_key", sa.Text(), nullable=True))
        if "music_filename" not in existing:
            op.add_column("events", sa.Column("music_filename", sa.String(length=512), nullable=True))
        if "music_mime_type" not in existing:
            op.add_column("events", sa.Column("music_mime_type", sa.String(length=128), nullable=True))

    if not inspector.has_table("event_activities"):
        op.create_table(
            "event_activities",
            sa.Column("id", sa.String(length=36), nullable=False),
            sa.Column("event_id", sa.String(length=36), nullable=False),
            sa.Column("text", sa.String(length=512), nullable=False),
            sa.Column("kind", sa.String(length=32), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.ForeignKeyConstraint(["event_id"], ["events.id"]),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index(op.f("ix_event_activities_event_id"), "event_activities", ["event_id"], unique=False)
        op.create_index(op.f("ix_event_activities_kind"), "event_activities", ["kind"], unique=False)


def downgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)

    if inspector.has_table("event_activities"):
        op.drop_index(op.f("ix_event_activities_kind"), table_name="event_activities")
        op.drop_index(op.f("ix_event_activities_event_id"), table_name="event_activities")
        op.drop_table("event_activities")

    if inspector.has_table("events"):
        existing = {column["name"] for column in inspector.get_columns("events")}
        if "music_mime_type" in existing:
            op.drop_column("events", "music_mime_type")
        if "music_filename" in existing:
            op.drop_column("events", "music_filename")
        if "music_storage_key" in existing:
            op.drop_column("events", "music_storage_key")
