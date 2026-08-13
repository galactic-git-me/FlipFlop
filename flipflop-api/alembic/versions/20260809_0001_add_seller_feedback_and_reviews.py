"""Add seller feedback + product review columns to gem_radar observations and scored listings

Revision ID: 20260809_0001
Revises: 20260808_0002
Create Date: 2026-08-09 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


revision = "20260809_0001"
down_revision = "20260808_0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Free eBay Browse API seller feedback — previously fetched and discarded.
    op.add_column("gem_radar_listing_observations", sa.Column("seller_feedback_percent", sa.Float(), nullable=True))
    op.add_column("gem_radar_listing_observations", sa.Column("seller_feedback_count", sa.Integer(), nullable=True))

    op.add_column("gem_radar_scored_listings", sa.Column("seller_feedback_percent", sa.Float(), nullable=True))
    op.add_column("gem_radar_scored_listings", sa.Column("seller_feedback_count", sa.Integer(), nullable=True))

    # Product review rating/count — SUPER_GEM/GEM-gated, eBay Catalog API, 7-day cached.
    op.add_column("gem_radar_scored_listings", sa.Column("review_average_rating", sa.Float(), nullable=True))
    op.add_column("gem_radar_scored_listings", sa.Column("review_count", sa.Integer(), nullable=True))


def downgrade() -> None:
    op.drop_column("gem_radar_scored_listings", "review_count")
    op.drop_column("gem_radar_scored_listings", "review_average_rating")
    op.drop_column("gem_radar_scored_listings", "seller_feedback_count")
    op.drop_column("gem_radar_scored_listings", "seller_feedback_percent")

    op.drop_column("gem_radar_listing_observations", "seller_feedback_count")
    op.drop_column("gem_radar_listing_observations", "seller_feedback_percent")
