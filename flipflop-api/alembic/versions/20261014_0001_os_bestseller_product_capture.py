"""Persist exact product-page captures for unpriced OS bestsellers.

Revision ID: 20261014_0001
Revises: 20261013_0002
"""
from alembic import op
import sqlalchemy as sa


revision = '20261014_0001'
down_revision = '20261013_0002'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('amazon_bestseller_observations', sa.Column('product_capture', sa.JSON(), nullable=True))


def downgrade():
    op.drop_column('amazon_bestseller_observations', 'product_capture')
