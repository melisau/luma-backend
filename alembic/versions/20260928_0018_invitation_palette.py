"""Per-event invitation palette overrides."""
from alembic import op
import sqlalchemy as sa
revision = "20260928_0018"
down_revision = "20260912_0017"
branch_labels = None
depends_on = None

def upgrade():
    columns = {c["name"] for c in sa.inspect(op.get_bind()).get_columns("events")}
    if "palette" not in columns:
        op.add_column("events", sa.Column("palette", sa.JSON(), nullable=False, server_default="{}"))

def downgrade():
    with op.batch_alter_table("events") as batch:
        batch.drop_column("palette")
