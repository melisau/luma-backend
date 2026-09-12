"""Selectable invitation opening."""
from alembic import op
import sqlalchemy as sa
revision = "20260912_0006"
down_revision = "20260912_0005"
branch_labels = None
depends_on = None

def upgrade():
    inspector = sa.inspect(op.get_bind())
    if inspector.has_table("events") and "opening_style" not in {c["name"] for c in inspector.get_columns("events")}:
        op.add_column("events", sa.Column("opening_style", sa.String(32), nullable=False, server_default="classic"))

def downgrade():
    with op.batch_alter_table("events") as batch:
        batch.drop_column("opening_style")
