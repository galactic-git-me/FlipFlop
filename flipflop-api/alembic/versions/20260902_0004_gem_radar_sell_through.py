"""Persist matched CPK sell-through evidence on Gem Radar decisions."""

from alembic import op
import sqlalchemy as sa


revision = "20260902_0004"
down_revision = "20260902_0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("gem_radar_scored_listings", sa.Column("active_listing_count", sa.Integer(), nullable=True))
    op.add_column("gem_radar_scored_listings", sa.Column("sold_listing_count", sa.Integer(), nullable=True))
    op.add_column("gem_radar_scored_listings", sa.Column("sell_through_rate_pct", sa.Float(), nullable=True))
    op.add_column("gem_radar_scored_listings", sa.Column("sell_through_window_days", sa.Integer(), nullable=True))
    op.add_column("gem_radar_scored_listings", sa.Column("sell_through_source", sa.String(length=64), nullable=True))


def downgrade() -> None:
    for column in (
        "sell_through_source", "sell_through_window_days", "sell_through_rate_pct",
        "sold_listing_count", "active_listing_count",
    ):
        op.drop_column("gem_radar_scored_listings", column)
