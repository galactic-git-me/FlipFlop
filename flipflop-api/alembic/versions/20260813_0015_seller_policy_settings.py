"""Add seller-policy fields to app_settings table

Revision ID: 20260813_0015
Revises: 20260813_0014
Create Date: 2026-08-13
"""
from alembic import op
import sqlalchemy as sa

revision = "20260813_0015"
down_revision = "20260813_0014"
depends_on = None


def upgrade():
    op.add_column('app_settings', sa.Column('handling_time_days', sa.Integer(), nullable=False, server_default='2'))
    op.add_column('app_settings', sa.Column('returns_accepted', sa.Boolean(), nullable=False, server_default=sa.true()))
    op.add_column('app_settings', sa.Column('returns_window_days', sa.Integer(), nullable=False, server_default='30'))
    op.add_column('app_settings', sa.Column('free_shipping_enabled', sa.Boolean(), nullable=False, server_default=sa.true()))
    op.add_column('app_settings', sa.Column('local_pickup_enabled', sa.Boolean(), nullable=False, server_default=sa.true()))
    op.add_column('app_settings', sa.Column('listing_type_default', sa.String(20), nullable=False, server_default='FixedPrice'))


def downgrade():
    for col in [
        'listing_type_default', 'local_pickup_enabled', 'free_shipping_enabled',
        'returns_window_days', 'returns_accepted', 'handling_time_days',
    ]:
        op.drop_column('app_settings', col)
