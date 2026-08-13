"""Add eBay seller OAuth (3-legged) token storage to app_settings

Revision ID: 20260813_0016
Revises: 20260813_0015
Create Date: 2026-08-13
"""
from alembic import op
import sqlalchemy as sa

revision = "20260813_0016"
down_revision = "20260813_0015"
depends_on = None


def upgrade():
    op.add_column('app_settings', sa.Column('ebay_seller_refresh_token', sa.Text(), nullable=False, server_default=''))
    op.add_column('app_settings', sa.Column('ebay_seller_refresh_token_expires_at', sa.DateTime(), nullable=True))
    op.add_column('app_settings', sa.Column('ebay_seller_access_token', sa.Text(), nullable=False, server_default=''))
    op.add_column('app_settings', sa.Column('ebay_seller_access_token_expires_at', sa.DateTime(), nullable=True))
    op.add_column('app_settings', sa.Column('ebay_seller_connected_at', sa.DateTime(), nullable=True))
    op.add_column('app_settings', sa.Column('ebay_seller_scopes', sa.Text(), nullable=False, server_default=''))


def downgrade():
    for col in [
        'ebay_seller_scopes', 'ebay_seller_connected_at', 'ebay_seller_access_token_expires_at',
        'ebay_seller_access_token', 'ebay_seller_refresh_token_expires_at', 'ebay_seller_refresh_token',
    ]:
        op.drop_column('app_settings', col)
