"""Add Gem Radar listing-observation ledger and seller-intelligence profiles

Backs price-history / watchlist change detection, relisting detection, and
cross-search score caching (PRD §23-25, §31) — see
gem-radar-extension/docs/ARCHITECTURE_GAP_ANALYSIS.md Slice X9.

Revision ID: 20260706_0015
Revises: 20260706_0014
Create Date: 2026-07-06
"""
from alembic import op
import sqlalchemy as sa

revision = "20260706_0015"
down_revision = "20260706_0014"
depends_on = None


def upgrade():
    op.create_table(
        "gem_radar_listing_observations",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("listing_id", sa.String(length=255), nullable=False),
        sa.Column("seller_name", sa.String(length=200), nullable=True),
        sa.Column("title", sa.String(length=500), nullable=False),
        sa.Column("category", sa.String(length=50), nullable=True),
        sa.Column("condition_normalised", sa.String(length=20), nullable=False),
        sa.Column("listing_type", sa.String(length=20), nullable=False),
        sa.Column("item_price", sa.Float(), nullable=False),
        sa.Column("postage_price", sa.Float(), nullable=False),
        sa.Column("delivered_price", sa.Float(), nullable=False),
        sa.Column("bid_count", sa.Integer(), nullable=True),
        sa.Column("best_offer_enabled", sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.Column("observed_at", sa.DateTime(), nullable=False),
        sa.Column("scored_result_json", sa.Text(), nullable=True),
        sa.Column("scored_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_gem_radar_listing_observations_listing_id", "gem_radar_listing_observations", ["listing_id"])
    op.create_index("ix_gem_radar_listing_observations_seller_name", "gem_radar_listing_observations", ["seller_name"])
    op.create_index("ix_gem_radar_listing_observations_observed_at", "gem_radar_listing_observations", ["observed_at"])

    op.create_table(
        "gem_radar_seller_profiles",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("seller_name", sa.String(length=200), nullable=False),
        sa.Column("feedback_percent", sa.Float(), nullable=True),
        sa.Column("feedback_count", sa.Integer(), nullable=True),
        sa.Column("seller_type", sa.String(length=20), nullable=True),
        sa.Column("observed_listings_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("historical_gem_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("historical_super_gem_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("historical_purchase_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("cancellation_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("issue_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("first_seen_at", sa.DateTime(), nullable=False),
        sa.Column("last_seen_at", sa.DateTime(), nullable=False),
    )
    op.create_index(
        "ix_gem_radar_seller_profiles_seller_name", "gem_radar_seller_profiles", ["seller_name"], unique=True
    )


def downgrade():
    op.drop_index("ix_gem_radar_seller_profiles_seller_name", table_name="gem_radar_seller_profiles")
    op.drop_table("gem_radar_seller_profiles")
    op.drop_index("ix_gem_radar_listing_observations_observed_at", table_name="gem_radar_listing_observations")
    op.drop_index("ix_gem_radar_listing_observations_seller_name", table_name="gem_radar_listing_observations")
    op.drop_index("ix_gem_radar_listing_observations_listing_id", table_name="gem_radar_listing_observations")
    op.drop_table("gem_radar_listing_observations")
