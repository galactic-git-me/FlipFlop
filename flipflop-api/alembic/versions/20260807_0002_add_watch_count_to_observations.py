"""Add watch_count to gem_radar_listing_observations

Revision ID: 20260807_0002
Revises: 20260807_0001
Create Date: 2026-08-07 22:16:00.000000

"""
from alembic import op
import sqlalchemy as sa


revision = "20260807_0002"
down_revision = "20260807_0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add watch_count column to gem_radar_listing_observations table
    op.add_column("gem_radar_listing_observations", sa.Column("watch_count", sa.Integer(), nullable=True, server_default="0"))


def downgrade() -> None:
    op.drop_column("gem_radar_listing_observations", "watch_count")
