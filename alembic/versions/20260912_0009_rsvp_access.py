"""Private RSVP editing credentials."""
from alembic import op
import sqlalchemy as sa
revision='20260912_0009'
down_revision='20260912_0008'
branch_labels=None
depends_on=None

def upgrade():
    if 'rsvp_token_hash' not in {c['name'] for c in sa.inspect(op.get_bind()).get_columns('guests')}:
        op.add_column('guests', sa.Column('rsvp_token_hash', sa.String(64), nullable=True))

def downgrade():
    with op.batch_alter_table('guests') as batch:
        batch.drop_column('rsvp_token_hash')
