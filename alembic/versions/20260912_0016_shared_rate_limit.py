"""Shared database rate limit buckets."""
from alembic import op
import sqlalchemy as sa
revision="20260912_0016";down_revision="20260912_0015";branch_labels=None;depends_on=None
def upgrade():
    if not sa.inspect(op.get_bind()).has_table("rate_limit_events"):
        op.create_table("rate_limit_events",sa.Column("id",sa.String(36),primary_key=True),sa.Column("bucket_key",sa.String(255),nullable=False),sa.Column("created_at",sa.DateTime(timezone=True),nullable=False));op.create_index("ix_rate_limit_events_bucket_key","rate_limit_events",["bucket_key"]);op.create_index("ix_rate_limit_events_created_at","rate_limit_events",["created_at"])
def downgrade(): op.drop_table("rate_limit_events")
