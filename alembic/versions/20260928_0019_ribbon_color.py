"""Custom satin ribbon color."""
from alembic import op
import sqlalchemy as sa
revision = "20260928_0019"
down_revision = "20260928_0018"
branch_labels = None
depends_on = None

def upgrade():
    columns = {column["name"] for column in sa.inspect(op.get_bind()).get_columns("events")}
    if "ribbon_color" not in columns:
        op.add_column("events", sa.Column("ribbon_color", sa.String(7), nullable=False, server_default="#718CA2"))

def downgrade():
    with op.batch_alter_table("events") as batch:
        batch.drop_column("ribbon_color")
