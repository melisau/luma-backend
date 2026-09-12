"""Event collaborators and guest seating."""
from alembic import op
import sqlalchemy as sa

revision = "20260912_0013"
down_revision = "20260912_0012"
branch_labels = None
depends_on = None


def upgrade():
    inspector = sa.inspect(op.get_bind())
    guest_columns = {column["name"] for column in inspector.get_columns("guests")}
    for name in ("group_name", "table_name"):
        if name not in guest_columns:
            op.add_column("guests", sa.Column(name, sa.String(255), nullable=False, server_default=""))
    if not inspector.has_table("event_members"):
        op.create_table(
            "event_members",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("event_id", sa.String(36), sa.ForeignKey("events.id"), nullable=False),
            sa.Column("admin_id", sa.String(36), sa.ForeignKey("admin_users.id"), nullable=False),
            sa.Column("role", sa.String(16), nullable=False, server_default="viewer"),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.UniqueConstraint("event_id", "admin_id", name="uq_event_member_admin"),
        )
        op.create_index("ix_event_members_event_id", "event_members", ["event_id"])
        op.create_index("ix_event_members_admin_id", "event_members", ["admin_id"])


def downgrade():
    op.drop_table("event_members")
    with op.batch_alter_table("guests") as batch:
        batch.drop_column("table_name")
        batch.drop_column("group_name")
