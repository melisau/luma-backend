"""Persist RSVP dietary requirements and notes."""
from alembic import op
import sqlalchemy as sa

revision = "20260912_0005"
down_revision = "20260812_0004"
branch_labels = None
depends_on = None


def upgrade():
    inspector = sa.inspect(op.get_bind())
    if not inspector.has_table("guests"):
        return
    columns = {column["name"] for column in inspector.get_columns("guests")}
    for name in ("dietary_requirements", "notes"):
        if name not in columns:
            op.add_column("guests", sa.Column(name, sa.Text(), nullable=False, server_default=""))


def downgrade():
    with op.batch_alter_table("guests") as batch:
        batch.drop_column("notes")
        batch.drop_column("dietary_requirements")
