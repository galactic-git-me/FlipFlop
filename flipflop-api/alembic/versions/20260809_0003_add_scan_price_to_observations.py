"""Add scan_price field to listing observations.

Revision ID: 20260809_0003
Revises: 20260808_0002
Create Date: 2026-08-09 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "20260809_0003"
down_revision = "20260808_0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "gem_radar_listing_observations",
        sa.Column("scan_price", sa.Float(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("gem_radar_listing_observations", "scan_price")
