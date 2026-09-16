"""Carry scraped delivery details into observations and scored listings.

Revision ID: 20260916_0001
Revises: 20260915_0001
"""
from alembic import op
import sqlalchemy as sa


revision = "20260916_0001"
down_revision = "20260915_0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "gem_radar_listing_observations",
        sa.Column("delivery_text", sa.String(length=500), nullable=True),
    )
    op.add_column(
        "gem_radar_listing_observations",
        sa.Column("delivery_postcode", sa.String(length=20), nullable=True),
    )
    op.add_column(
        "gem_radar_scored_listings",
        sa.Column("delivery_text", sa.String(length=500), nullable=True),
    )
    op.add_column(
        "gem_radar_scored_listings",
        sa.Column("delivery_postcode", sa.String(length=20), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("gem_radar_scored_listings", "delivery_postcode")
    op.drop_column("gem_radar_scored_listings", "delivery_text")
    op.drop_column("gem_radar_listing_observations", "delivery_postcode")
    op.drop_column("gem_radar_listing_observations", "delivery_text")
