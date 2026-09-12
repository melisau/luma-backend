"""Opt-in memory retention."""
from alembic import op
import sqlalchemy as sa
revision='20260912_0012'
down_revision='20260912_0011'
branch_labels=None
depends_on=None

def upgrade():
    columns={c['name'] for c in sa.inspect(op.get_bind()).get_columns('events')}
    for name in ['memory_delete_at','memory_purged_at']:
        if name not in columns:op.add_column('events',sa.Column(name,sa.DateTime(timezone=True),nullable=True))

def downgrade():
    with op.batch_alter_table('events') as batch:
        batch.drop_column('memory_delete_at');batch.drop_column('memory_purged_at')
