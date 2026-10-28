"""Keep unknown supplier prices unknown instead of inventing zero prices."""
from alembic import op
import sqlalchemy as sa

revision = '20261027_0002'
down_revision = '20261027_0001'
branch_labels = None
depends_on = None

def upgrade():
    op.alter_column('listings','price',existing_type=sa.Float(),nullable=True)

def downgrade():
    if op.get_bind().execute(sa.text('SELECT EXISTS(SELECT 1 FROM listings WHERE price IS NULL)')).scalar_one():
        raise RuntimeError('Cannot restore required prices while unknown catalogue prices exist')
    op.alter_column('listings','price',existing_type=sa.Float(),nullable=False)
