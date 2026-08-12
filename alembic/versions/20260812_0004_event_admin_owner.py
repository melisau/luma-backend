"""event admin ownership

Revision ID: 20260812_0004
Revises: 20260812_0003
Create Date: 2026-08-12

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect, text

revision: str = "20260812_0004"
down_revision: Union[str, None] = "20260812_0003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    if not inspector.has_table("events") or not inspector.has_table("admin_users"):
        return

    existing = {column["name"] for column in inspector.get_columns("events")}
    if "admin_id" not in existing:
        op.add_column("events", sa.Column("admin_id", sa.String(length=36), nullable=True))
        op.create_index("ix_events_admin_id", "events", ["admin_id"], unique=False)
        bind.execute(
            text(
                """
                UPDATE events
                SET admin_id = (
                    SELECT id FROM admin_users ORDER BY created_at ASC LIMIT 1
                )
                WHERE admin_id IS NULL
                """
            )
        )
        with op.batch_alter_table("events") as batch_op:
            batch_op.create_foreign_key("fk_events_admin_id", "admin_users", ["admin_id"], ["id"])
            batch_op.alter_column("admin_id", nullable=False)
            batch_op.create_unique_constraint("uq_admin_event_slug", ["admin_id", "slug"])


def downgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    if not inspector.has_table("events"):
        return
    existing = {column["name"] for column in inspector.get_columns("events")}
    if "admin_id" in existing:
        with op.batch_alter_table("events") as batch_op:
            batch_op.drop_constraint("uq_admin_event_slug", type_="unique")
            batch_op.drop_constraint("fk_events_admin_id", type_="foreignkey")
            batch_op.drop_index("ix_events_admin_id")
            batch_op.drop_column("admin_id")
