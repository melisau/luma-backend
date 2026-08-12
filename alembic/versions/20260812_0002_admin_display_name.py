"""admin display name column

Revision ID: 20260812_0002
Revises: 20260812_0001
Create Date: 2026-08-12

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

revision: str = "20260812_0002"
down_revision: Union[str, None] = "20260812_0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    if not inspector.has_table("admin_users"):
        return
    existing = {column["name"] for column in inspector.get_columns("admin_users")}
    if "display_name" not in existing:
        op.add_column("admin_users", sa.Column("display_name", sa.String(length=255), nullable=True))


def downgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    if inspector.has_table("admin_users"):
        existing = {column["name"] for column in inspector.get_columns("admin_users")}
        if "display_name" in existing:
            op.drop_column("admin_users", "display_name")
