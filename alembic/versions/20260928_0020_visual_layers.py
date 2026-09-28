"""Invitation image layers and owned uploads."""
from alembic import op
import sqlalchemy as sa
revision = "20260928_0020"
down_revision = "20260928_0019"
branch_labels = None
depends_on = None

def upgrade():
    columns = {c["name"] for c in sa.inspect(op.get_bind()).get_columns("events")}
    for name in ("visual_layers", "visual_assets"):
        if name not in columns:
            op.add_column("events", sa.Column(name, sa.JSON(), nullable=False, server_default="[]"))

def downgrade():
    with op.batch_alter_table("events") as batch:
        batch.drop_column("visual_layers")
        batch.drop_column("visual_assets")
