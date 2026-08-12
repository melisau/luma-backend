"""guestbook message moderation status

Revision ID: 20260812_0003
Revises: 20260812_0002
Create Date: 2026-08-12

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

revision: str = "20260812_0003"
down_revision: Union[str, None] = "20260812_0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    if not inspector.has_table("guestbook_messages"):
        return
    existing = {column["name"] for column in inspector.get_columns("guestbook_messages")}
    if "status" not in existing:
        op.add_column(
            "guestbook_messages",
            sa.Column("status", sa.String(length=32), nullable=False, server_default="approved"),
        )
        op.create_index("ix_guestbook_messages_status", "guestbook_messages", ["status"], unique=False)


def downgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    if inspector.has_table("guestbook_messages"):
        existing = {column["name"] for column in inspector.get_columns("guestbook_messages")}
        if "status" in existing:
            op.drop_index("ix_guestbook_messages_status", table_name="guestbook_messages")
            op.drop_column("guestbook_messages", "status")
