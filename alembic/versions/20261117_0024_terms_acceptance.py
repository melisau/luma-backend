"""Record when and which version of the terms of use an owner accepted at sign-up."""
from alembic import op
import sqlalchemy as sa

revision = "20261117_0024"
down_revision = "20261118_0027"
branch_labels = None
depends_on = None

COLUMNS = {
    "terms_accepted_at": lambda: sa.Column("terms_accepted_at", sa.DateTime(timezone=True), nullable=True),
    "terms_version": lambda: sa.Column("terms_version", sa.String(32), nullable=True),
}


def upgrade():
    inspector = sa.inspect(op.get_bind())
    if not inspector.has_table("admin_users"):
        return
    existing = {column["name"] for column in inspector.get_columns("admin_users")}
    for name, column in COLUMNS.items():
        if name not in existing:
            op.add_column("admin_users", column())


def downgrade():
    inspector = sa.inspect(op.get_bind())
    if not inspector.has_table("admin_users"):
        return
    existing = {column["name"] for column in inspector.get_columns("admin_users")}
    with op.batch_alter_table("admin_users") as batch:
        for name in COLUMNS:
            if name in existing:
                batch.drop_column(name)
