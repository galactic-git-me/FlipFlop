"""Add video upload fields to flips table (row 41)

Revision ID: 20260813_0018
Revises: 20260813_0017
Create Date: 2026-08-13
"""
from alembic import op
import sqlalchemy as sa

revision = "20260813_0018"
down_revision = "20260813_0017"
depends_on = None


def upgrade():
    op.add_column('flips', sa.Column('generated_video_url', sa.String(500), nullable=True))
    op.add_column('flips', sa.Column('video_ebay_status', sa.String(50), nullable=True))


def downgrade():
    op.drop_column('flips', 'video_ebay_status')
    op.drop_column('flips', 'generated_video_url')
