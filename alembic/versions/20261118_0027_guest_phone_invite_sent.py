"""Guest phone (for WhatsApp) and when the personal link was sent."""
from alembic import op
import sqlalchemy as sa

revision = "20261118_0027"
down_revision = "20261117_0026"
branch_labels = None
depends_on = None

COLUMNS = {
    "phone": lambda: sa.Column("phone", sa.String(32), nullable=False, server_default=""),
    "invite_sent_at": lambda: sa.Column("invite_sent_at", sa.DateTime(timezone=True), nullable=True),
}


def upgrade():
    inspector = sa.inspect(op.get_bind())
    if not inspector.has_table("guests"):
        return
    existing = {column["name"] for column in inspector.get_columns("guests")}
    for name, column in COLUMNS.items():
        if name not in existing:
            op.add_column("guests", column())


def downgrade():
    inspector = sa.inspect(op.get_bind())
    if not inspector.has_table("guests"):
        return
    existing = {column["name"] for column in inspector.get_columns("guests")}
    with op.batch_alter_table("guests") as batch:
        for name in COLUMNS:
            if name in existing:
                batch.drop_column(name)
