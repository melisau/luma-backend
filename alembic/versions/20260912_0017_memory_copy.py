"""Custom memory section copy."""
from alembic import op
import sqlalchemy as sa
revision="20260912_0017";down_revision="20260912_0016";branch_labels=None;depends_on=None
def upgrade():
    columns={c["name"] for c in sa.inspect(op.get_bind()).get_columns("events")}
    if "memory_title" not in columns: op.add_column("events",sa.Column("memory_title",sa.String(255),nullable=False,server_default="Gözünden bizim hikâyemiz."))
    if "memory_text" not in columns: op.add_column("events",sa.Column("memory_text",sa.Text(),nullable=False,server_default=""))
def downgrade():
    with op.batch_alter_table("events") as batch: batch.drop_column("memory_text");batch.drop_column("memory_title")
