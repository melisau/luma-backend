"""Record when a guest gave explicit consent for their dietary information (KVKK m.6)."""
from alembic import op
import sqlalchemy as sa

revision = "20261116_0023"
down_revision = "20261024_0022"
branch_labels = None
depends_on = None


def upgrade():
    inspector = sa.inspect(op.get_bind())
    if not inspector.has_table("guests"):
        return
    columns = {column["name"] for column in inspector.get_columns("guests")}
    if "dietary_consent_at" not in columns:
        op.add_column("guests", sa.Column("dietary_consent_at", sa.DateTime(timezone=True), nullable=True))


def downgrade():
    inspector = sa.inspect(op.get_bind())
    if not inspector.has_table("guests"):
        return
    columns = {column["name"] for column in inspector.get_columns("guests")}
    if "dietary_consent_at" in columns:
        with op.batch_alter_table("guests") as batch:
            batch.drop_column("dietary_consent_at")
