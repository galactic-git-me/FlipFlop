"""Create component_catalogue and vendor_prices tables

Revision ID: 20260628_0004
Revises: 20260628_0003
Create Date: 2026-06-28 00:00:03.000000

"""
from alembic import op
import sqlalchemy as sa


revision = '20260628_0004'
down_revision = '20260628_0003'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'component_catalogue',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('category', sa.String(), nullable=False),
        sa.Column('manufacturer', sa.String(), nullable=False),
        sa.Column('model', sa.String(), nullable=False),
        sa.Column('variant', sa.String(), nullable=True),
        sa.Column('market_price', sa.Float(), nullable=False),
        sa.Column('used_market_price', sa.Float(), nullable=True),
        sa.Column('search_volume', sa.Float(), server_default='0.0'),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_component_catalogue_category', 'component_catalogue', ['category'])

    op.create_table(
        'vendor_prices',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('component_id', sa.Integer(), nullable=False),
        sa.Column('vendor', sa.String(), nullable=False),
        sa.Column('price', sa.Float(), nullable=False),
        sa.Column('stock_status', sa.String(), nullable=False),
        sa.Column('lead_time_days', sa.Integer(), nullable=False),
        sa.Column('url', sa.String(), nullable=True),
        sa.Column('last_updated', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['component_id'], ['component_catalogue.id']),
        sa.PrimaryKeyConstraint('id')
    )


def downgrade():
    op.drop_table('vendor_prices')
    op.drop_index('ix_component_catalogue_category')
    op.drop_table('component_catalogue')
