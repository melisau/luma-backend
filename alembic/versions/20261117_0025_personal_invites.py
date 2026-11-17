"""Personal invitation links bound to guests' devices."""
from alembic import op
import sqlalchemy as sa

revision = "20261117_0025"
down_revision = "20261116_0023"
branch_labels = None
depends_on = None

EVENT_COLUMNS = {
    "invite_mode": lambda: sa.Column("invite_mode", sa.String(16), nullable=False, server_default="open"),
    "upload_key": lambda: sa.Column("upload_key", sa.String(64), nullable=True),
}
GUEST_COLUMNS = {
    "invite_version": lambda: sa.Column("invite_version", sa.Integer(), nullable=False, server_default="0"),
    "access_code_hash": lambda: sa.Column("access_code_hash", sa.String(64), nullable=True),
    "access_code_expires_at": lambda: sa.Column("access_code_expires_at", sa.DateTime(timezone=True), nullable=True),
    "access_code_attempts": lambda: sa.Column("access_code_attempts", sa.Integer(), nullable=False, server_default="0"),
    "access_code_sent_at": lambda: sa.Column("access_code_sent_at", sa.DateTime(timezone=True), nullable=True),
}


def _add(inspector, table, columns):
    if not inspector.has_table(table):
        return
    existing = {column["name"] for column in inspector.get_columns(table)}
    for name, column in columns.items():
        if name not in existing:
            op.add_column(table, column())


def upgrade():
    inspector = sa.inspect(op.get_bind())
    _add(inspector, "events", EVENT_COLUMNS)
    _add(inspector, "guests", GUEST_COLUMNS)
    if inspector.has_table("guests") and not inspector.has_table("guest_devices"):
        op.create_table(
            "guest_devices",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("guest_id", sa.String(36), sa.ForeignKey("guests.id", ondelete="CASCADE"), nullable=False, index=True),
            sa.Column("secret_hash", sa.String(64), nullable=False, unique=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=False),
        )


def downgrade():
    inspector = sa.inspect(op.get_bind())
    if inspector.has_table("guest_devices"):
        op.drop_table("guest_devices")
    for table, columns in (("guests", GUEST_COLUMNS), ("events", EVENT_COLUMNS)):
        if not inspector.has_table(table):
            continue
        existing = {column["name"] for column in inspector.get_columns(table)}
        with op.batch_alter_table(table) as batch:
            for name in columns:
                if name in existing:
                    batch.drop_column(name)
