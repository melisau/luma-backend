"""Optional invitation paper and photo exhibition."""
from alembic import op
import sqlalchemy as sa
revision = "20260928_0021"
down_revision = "20260928_0020"
branch_labels = None
depends_on = None

def upgrade():
    if "presentation" not in {c["name"] for c in sa.inspect(op.get_bind()).get_columns("events")}:
        op.add_column("events", sa.Column("presentation", sa.JSON(), nullable=False, server_default="{}"))

def downgrade():
    with op.batch_alter_table("events") as batch:
        batch.drop_column("presentation")
