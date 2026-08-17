"""Opportunity scoring, canonical current rows and component feedback.

Revision ID: 20260817_0001
Revises: 20260814_0004, 6ce7c69805a2
"""
from alembic import op
import sqlalchemy as sa

revision = "20260817_0001"
down_revision = ("20260814_0004", "6ce7c69805a2")
branch_labels = None
depends_on = None


def upgrade():
    op.alter_column("gem_radar_listing_demand_history", "watch_count", existing_type=sa.Integer(), nullable=True, server_default=None)
    op.alter_column("gem_radar_listing_demand_history", "bid_count", existing_type=sa.Integer(), nullable=True, server_default=None)
    score_float_columns = (
        "expected_profit", "roi_pct", "walk_away_price", "conservative_resale_price",
        "market_confidence", "market_spread_pct", "liquidity_score", "desirability_score", "risk_score",
    )
    for name in score_float_columns:
        op.add_column("gem_radar_scored_listings", sa.Column(name, sa.Float(), nullable=True))
    op.add_column("gem_radar_scored_listings", sa.Column("market_sample_size", sa.Integer(), nullable=True))
    op.add_column("gem_radar_scored_listings", sa.Column("market_source_diversity", sa.Integer(), nullable=True))
    op.add_column("gem_radar_scored_listings", sa.Column("eligible", sa.Boolean(), nullable=False, server_default=sa.false()))
    op.add_column("gem_radar_scored_listings", sa.Column("scoring_explanation", sa.JSON(), nullable=True))

    # Back up redundant scored rows inside the database before consolidation.
    op.execute("CREATE TABLE gem_radar_scored_listings_dedup_backup_20260817 AS TABLE gem_radar_scored_listings")
    op.execute("""
        DELETE FROM gem_radar_scored_listings older
        USING gem_radar_scored_listings newer
        WHERE older.listing_id = newer.listing_id
          AND (older.scored_at, older.id) < (newer.scored_at, newer.id)
    """)
    op.create_unique_constraint("uq_gem_radar_scored_listing_listing_id", "gem_radar_scored_listings", ["listing_id"])

    settings = {
        "opportunity_super_profit_gbp": (sa.Float(), "50"), "opportunity_super_roi_pct": (sa.Float(), "25"),
        "opportunity_super_confidence": (sa.Float(), "80"), "opportunity_super_liquidity": (sa.Float(), "60"),
        "opportunity_super_score": (sa.Float(), "85"), "opportunity_gem_profit_gbp": (sa.Float(), "30"),
        "opportunity_gem_roi_pct": (sa.Float(), "18"), "opportunity_gem_confidence": (sa.Float(), "70"),
        "opportunity_gem_liquidity": (sa.Float(), "45"), "opportunity_gem_score": (sa.Float(), "75"),
        "opportunity_delivery_fallback_gbp": (sa.Float(), "15"), "opportunity_ebay_fee_pct": (sa.Float(), "0"),
        "opportunity_packaging_gbp": (sa.Float(), "6"), "opportunity_testing_refurbishment_gbp": (sa.Float(), "10"),
        "opportunity_returns_warranty_pct": (sa.Float(), "5"), "opportunity_minimum_sold_comps": (sa.Integer(), "5"),
        "opportunity_minimum_source_diversity": (sa.Integer(), "2"),
    }
    for name, (kind, default) in settings.items():
        op.add_column("app_settings", sa.Column(name, kind, nullable=False, server_default=default))

    op.create_table("gem_radar_decision_events",
        sa.Column("id", sa.Integer(), primary_key=True), sa.Column("listing_id", sa.String(255), nullable=False, index=True),
        sa.Column("classification", sa.String(50), nullable=False, index=True), sa.Column("decision", sa.String(50), nullable=False),
        sa.Column("score", sa.Float(), nullable=False), sa.Column("explanation", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False, index=True))
    op.create_table("component_rating_events",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("build_id", sa.Integer(), sa.ForeignKey("manual_builds.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("component_slot", sa.String(50), nullable=False), sa.Column("component_key", sa.String(255), nullable=False, index=True),
        sa.Column("overall_rating", sa.Integer(), nullable=False), sa.Column("reliability_rating", sa.Integer()),
        sa.Column("installation_rating", sa.Integer()), sa.Column("aesthetics_rating", sa.Integer()),
        sa.Column("value_rating", sa.Integer()), sa.Column("customer_appeal_rating", sa.Integer()),
        sa.Column("notes", sa.Text()), sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("build_id", "component_slot", "component_key", name="uq_component_rating_build_slot_key"))
    op.create_table("preferred_components",
        sa.Column("component_key", sa.String(255), primary_key=True), sa.Column("component_slot", sa.String(50), nullable=False, index=True),
        sa.Column("sample_count", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("average_rating", sa.Float(), nullable=False, server_default="5"),
        sa.Column("status", sa.String(20), nullable=False, server_default="preferred"),
        sa.Column("last_build_id", sa.Integer()), sa.Column("last_used_at", sa.DateTime(), nullable=False),
        sa.Column("outcome_summary", sa.JSON()))


def downgrade():
    op.execute("UPDATE gem_radar_listing_demand_history SET watch_count = 0 WHERE watch_count IS NULL")
    op.execute("UPDATE gem_radar_listing_demand_history SET bid_count = 0 WHERE bid_count IS NULL")
    op.alter_column("gem_radar_listing_demand_history", "watch_count", existing_type=sa.Integer(), nullable=False, server_default="0")
    op.alter_column("gem_radar_listing_demand_history", "bid_count", existing_type=sa.Integer(), nullable=False, server_default="0")
    op.drop_table("preferred_components")
    op.drop_table("component_rating_events")
    op.drop_table("gem_radar_decision_events")
    for name in (
        "opportunity_super_profit_gbp", "opportunity_super_roi_pct", "opportunity_super_confidence",
        "opportunity_super_liquidity", "opportunity_super_score", "opportunity_gem_profit_gbp",
        "opportunity_gem_roi_pct", "opportunity_gem_confidence", "opportunity_gem_liquidity",
        "opportunity_gem_score", "opportunity_delivery_fallback_gbp", "opportunity_ebay_fee_pct",
        "opportunity_packaging_gbp", "opportunity_testing_refurbishment_gbp",
        "opportunity_returns_warranty_pct", "opportunity_minimum_sold_comps",
        "opportunity_minimum_source_diversity"):
        op.drop_column("app_settings", name)
    op.drop_constraint("uq_gem_radar_scored_listing_listing_id", "gem_radar_scored_listings", type_="unique")
    for name in ("expected_profit", "roi_pct", "walk_away_price", "conservative_resale_price", "market_confidence",
                 "market_spread_pct", "liquidity_score", "desirability_score", "risk_score", "market_sample_size",
                 "market_source_diversity", "eligible", "scoring_explanation"):
        op.drop_column("gem_radar_scored_listings", name)
