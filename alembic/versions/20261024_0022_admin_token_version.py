"""Invalidate administrator sessions after password changes."""
from alembic import op
import sqlalchemy as sa

revision = "20261024_0022"
down_revision = "20260928_0021"
branch_labels = None
depends_on = None


def upgrade():
    inspector = sa.inspect(op.get_bind())
    if not inspector.has_table("admin_users"):
        return
    columns = {column["name"] for column in inspector.get_columns("admin_users")}
    if "token_version" not in columns:
        op.add_column(
            "admin_users",
            sa.Column("token_version", sa.Integer(), nullable=False, server_default="0"),
        )


def downgrade():
    inspector = sa.inspect(op.get_bind())
    if not inspector.has_table("admin_users"):
        return
    columns = {column["name"] for column in inspector.get_columns("admin_users")}
    if "token_version" in columns:
        with op.batch_alter_table("admin_users") as batch:
            batch.drop_column("token_version")
