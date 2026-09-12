"""Invitation logistics."""
from alembic import op
import sqlalchemy as sa
revision='20260912_0008'
down_revision='20260912_0007'
branch_labels=None
depends_on=None
FIELDS=('address','transport_notes','contact_info','schedule')
def upgrade():
    existing={c['name'] for c in sa.inspect(op.get_bind()).get_columns('events')}
    for name in FIELDS:
        if name not in existing:
            op.add_column('events',sa.Column(name,sa.Text(),nullable=False,server_default=''))
def downgrade():
    with op.batch_alter_table('events') as batch:
        for name in FIELDS:
            batch.drop_column(name)
