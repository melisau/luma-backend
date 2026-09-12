"""Invitation access and album privacy."""
from alembic import op
import sqlalchemy as sa
revision='20260912_0011'
down_revision='20260912_0010'
branch_labels=None
depends_on=None

def upgrade():
    columns={c['name'] for c in sa.inspect(op.get_bind()).get_columns('events')}
    if 'access_code_hash' not in columns:
        op.add_column('events',sa.Column('access_code_hash',sa.String(255),nullable=True))
    if 'album_public' not in columns:
        op.add_column('events',sa.Column('album_public',sa.Boolean(),nullable=False,server_default=sa.true()))

def downgrade():
    with op.batch_alter_table('events') as batch:
        batch.drop_column('access_code_hash');batch.drop_column('album_public')
