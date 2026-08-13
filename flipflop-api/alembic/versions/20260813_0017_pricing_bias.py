"""Create pricing_bias table (row 49 fast-sale anchor bias)

Revision ID: 20260813_0017
Revises: 20260813_0016
Create Date: 2026-08-13
"""
from alembic import op
import sqlalchemy as sa

revision = "20260813_0017"
down_revision = "20260813_0016"
depends_on = None


def upgrade():
    op.create_table(
        'pricing_bias',
        sa.Column('cpu_tier', sa.String(50), primary_key=True),
        sa.Column('anchor_bias_pct', sa.Float(), nullable=False, server_default='0.0'),
        sa.Column('triggered_by_flip_id', sa.Integer(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
    )


def downgrade():
    op.drop_table('pricing_bias')
