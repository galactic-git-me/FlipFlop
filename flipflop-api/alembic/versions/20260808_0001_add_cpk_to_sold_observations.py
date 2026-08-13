"""Add cpk column to gem_radar_sold_observations for market price aggregation

Revision ID: 20260808_0001
Revises: 20260807_0002
Create Date: 2026-08-08 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


revision = "20260808_0001"
down_revision = "20260807_0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add cpk column to allow sold observations to contribute to CPK market price aggregation
    op.add_column("gem_radar_sold_observations", sa.Column("cpk", sa.String(255), nullable=True))
    # Index on cpk for faster market price lookups
    op.create_index("ix_gem_radar_sold_obs_cpk", "gem_radar_sold_observations", ["cpk"])


def downgrade() -> None:
    op.drop_index("ix_gem_radar_sold_obs_cpk", "gem_radar_sold_observations")
    op.drop_column("gem_radar_sold_observations", "cpk")
