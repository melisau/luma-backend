"""Email verification, password reset and RSVP reminders."""
from alembic import op
import sqlalchemy as sa
revision="20260912_0015";down_revision="20260912_0014";branch_labels=None;depends_on=None
def upgrade():
    inspector=sa.inspect(op.get_bind())
    if "email_verified_at" not in {c["name"] for c in inspector.get_columns("admin_users")}: op.add_column("admin_users",sa.Column("email_verified_at",sa.DateTime(timezone=True),nullable=True))
    event_columns={c["name"] for c in inspector.get_columns("events")}
    if "rsvp_reminder_at" not in event_columns: op.add_column("events",sa.Column("rsvp_reminder_at",sa.DateTime(timezone=True),nullable=True))
    if "rsvp_reminder_sent_at" not in event_columns: op.add_column("events",sa.Column("rsvp_reminder_sent_at",sa.DateTime(timezone=True),nullable=True))
    if not inspector.has_table("account_tokens"):
        op.create_table("account_tokens",sa.Column("id",sa.String(36),primary_key=True),sa.Column("admin_id",sa.String(36),sa.ForeignKey("admin_users.id"),nullable=False),sa.Column("token_hash",sa.String(64),nullable=False),sa.Column("purpose",sa.String(24),nullable=False),sa.Column("expires_at",sa.DateTime(timezone=True),nullable=False),sa.Column("used_at",sa.DateTime(timezone=True)),sa.Column("created_at",sa.DateTime(timezone=True),nullable=False))
        op.create_index("ix_account_tokens_admin_id","account_tokens",["admin_id"]);op.create_index("ix_account_tokens_token_hash","account_tokens",["token_hash"],unique=True);op.create_index("ix_account_tokens_purpose","account_tokens",["purpose"])
def downgrade():
    op.drop_table("account_tokens")
    with op.batch_alter_table("events") as batch: batch.drop_column("rsvp_reminder_sent_at");batch.drop_column("rsvp_reminder_at")
    with op.batch_alter_table("admin_users") as batch: batch.drop_column("email_verified_at")
