"""Slide show of approved photos, curated by the event owner."""
from alembic import op
import sqlalchemy as sa

revision = "20261117_0026"
down_revision = "20261117_0025"
branch_labels = None
depends_on = None


def upgrade():
    inspector = sa.inspect(op.get_bind())
    if not inspector.has_table("events"):
        return
    if "slideshow" not in {column["name"] for column in inspector.get_columns("events")}:
        op.add_column("events", sa.Column("slideshow", sa.JSON(), nullable=False, server_default="{}"))


def downgrade():
    inspector = sa.inspect(op.get_bind())
    if inspector.has_table("events") and "slideshow" in {column["name"] for column in inspector.get_columns("events")}:
        with op.batch_alter_table("events") as batch:
            batch.drop_column("slideshow")
