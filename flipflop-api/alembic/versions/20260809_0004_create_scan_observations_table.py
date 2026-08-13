"""Create gem_radar_scan_observation table for barcode scan prices.

Revision ID: 20260809_0004
Revises: 20260809_0003
Create Date: 2026-08-09 12:01:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "20260809_0004"
down_revision = "20260809_0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "gem_radar_scan_observation",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("cpk", sa.String(64), nullable=True),
        sa.Column("match_key", sa.String(255), nullable=False),
        sa.Column("category", sa.String(50), nullable=True),
        sa.Column("brand", sa.String(100), nullable=True),
        sa.Column("model", sa.String(200), nullable=True),
        sa.Column("price", sa.Float(), nullable=False),
        sa.Column("observed_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_gem_radar_scan_observation_cpk", "gem_radar_scan_observation", ["cpk"])
    op.create_index("ix_gem_radar_scan_observation_match_key", "gem_radar_scan_observation", ["match_key"])
    op.create_index("ix_gem_radar_scan_observation_observed_at", "gem_radar_scan_observation", ["observed_at"])


def downgrade() -> None:
    op.drop_index("ix_gem_radar_scan_observation_observed_at", table_name="gem_radar_scan_observation")
    op.drop_index("ix_gem_radar_scan_observation_match_key", table_name="gem_radar_scan_observation")
    op.drop_index("ix_gem_radar_scan_observation_cpk", table_name="gem_radar_scan_observation")
    op.drop_table("gem_radar_scan_observation")
