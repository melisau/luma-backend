"""Envelope appearance settings."""
from alembic import op
import sqlalchemy as sa
revision="20260912_0007"
down_revision="20260912_0006"
branch_labels=None
depends_on=None
DEFAULTS={'envelope_color': '#e9dcc4', 'seal_color': '#873f43', 'paper_color': '#fffdf7', 'envelope_texture': 'linen', 'envelope_pattern': 'plain', 'seal_motif': 'botanical'}
def upgrade():
    inspector=sa.inspect(op.get_bind())
    columns={c['name'] for c in inspector.get_columns('events')}
    for name,value in DEFAULTS.items():
        if name not in columns:
            op.add_column('events',sa.Column(name,sa.String(20),nullable=False,server_default=value))
def downgrade():
    with op.batch_alter_table('events') as batch:
        for name in DEFAULTS:
            batch.drop_column(name)
