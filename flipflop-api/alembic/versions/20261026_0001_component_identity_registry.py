"""Stable component identity registry and independently evidenced identifiers."""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = '20261026_0001'
down_revision = '20261023_0003'
branch_labels = None
depends_on = None

def upgrade():
    op.create_table('canonical_component_products',
        sa.Column('cpk',sa.String(64),primary_key=True),
        sa.Column('identity',postgresql.JSONB(),nullable=False),
        sa.Column('created_at',sa.DateTime(),server_default=sa.func.now(),nullable=False))
    op.create_table('canonical_component_identifiers',
        sa.Column('kind',sa.String(20),primary_key=True),
        sa.Column('namespace',sa.String(100),primary_key=True),
        sa.Column('value',sa.String(255),primary_key=True),
        sa.Column('cpk',sa.String(64),sa.ForeignKey('canonical_component_products.cpk'),nullable=False,index=True),
        sa.Column('evidence',postgresql.JSONB(),nullable=False),
        sa.Column('created_at',sa.DateTime(),server_default=sa.func.now(),nullable=False))

def downgrade():
    op.drop_table('canonical_component_identifiers')
    op.drop_table('canonical_component_products')
