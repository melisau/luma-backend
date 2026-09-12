"""Event scoped photo deduplication."""
from alembic import op
import sqlalchemy as sa
revision='20260912_0010'
down_revision='20260912_0009'
branch_labels=None
depends_on=None

def upgrade():
    inspector=sa.inspect(op.get_bind())
    if 'content_hash' not in {c['name'] for c in inspector.get_columns('photos')}:
        op.add_column('photos',sa.Column('content_hash',sa.String(64),nullable=True))
    if 'uq_event_photo_hash' not in {c['name'] for c in inspector.get_unique_constraints('photos')}:
        with op.batch_alter_table('photos') as batch:
            batch.create_unique_constraint('uq_event_photo_hash',['event_id','content_hash'])

def downgrade():
    with op.batch_alter_table('photos') as batch:
        batch.drop_constraint('uq_event_photo_hash',type_='unique')
        batch.drop_column('content_hash')
