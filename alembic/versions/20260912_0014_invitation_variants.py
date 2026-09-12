"""Invitation signature, memory cover, language, theme and scheduling."""
from alembic import op
import sqlalchemy as sa

revision = "20260912_0014"
down_revision = "20260912_0013"
branch_labels = None
depends_on = None


def upgrade():
    columns = {column["name"] for column in sa.inspect(op.get_bind()).get_columns("events")}
    definitions = {
        "signature_text": sa.Column("signature_text", sa.String(255), nullable=False, server_default=""),
        "memory_cover_storage_key": sa.Column("memory_cover_storage_key", sa.Text(), nullable=True),
        "language": sa.Column("language", sa.String(8), nullable=False, server_default="tr"),
        "design_theme": sa.Column("design_theme", sa.String(32), nullable=False, server_default="romantic"),
        "publish_at": sa.Column("publish_at", sa.DateTime(timezone=True), nullable=True),
    }
    for name, column in definitions.items():
        if name not in columns:
            op.add_column("events", column)


def downgrade():
    with op.batch_alter_table("events") as batch:
        for name in ("publish_at", "design_theme", "language", "memory_cover_storage_key", "signature_text"):
            batch.drop_column(name)
