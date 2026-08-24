"""Add pricing, offer, recreate-cycle, and promotion fields to manual builds.

Revision ID: 20260824_0008
Revises: 20260823_0007
Create Date: 2026-08-24
"""

from alembic import op
import sqlalchemy as sa


revision = "20260824_0008"
down_revision = "20260823_0007"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("manual_builds", sa.Column("sold_comp_target", sa.Float(), nullable=True))
    op.add_column("manual_builds", sa.Column("active_range_ceiling", sa.Float(), nullable=True))
    op.add_column("manual_builds", sa.Column("price_floor", sa.Float(), nullable=True))
    op.add_column("manual_builds", sa.Column("price_last_recalculated_at", sa.DateTime(), nullable=True))
    op.add_column("manual_builds", sa.Column("price_floor_hit_review_needed", sa.Boolean(), nullable=False, server_default=sa.false()))
    op.add_column("manual_builds", sa.Column("demand_sold_count_90d", sa.Integer(), nullable=True))
    op.add_column("manual_builds", sa.Column("demand_active_count", sa.Integer(), nullable=True))
    op.add_column("manual_builds", sa.Column("demand_checked_at", sa.DateTime(), nullable=True))
    op.add_column("manual_builds", sa.Column("last_counter_offer_price", sa.Float(), nullable=True))
    op.add_column("manual_builds", sa.Column("counter_offer_round", sa.Integer(), nullable=False, server_default="0"))
    op.add_column("manual_builds", sa.Column("last_watcher_offer_sent_at", sa.DateTime(), nullable=True))
    op.add_column("manual_builds", sa.Column("recreate_cycle_count", sa.Integer(), nullable=False, server_default="0"))
    op.add_column("manual_builds", sa.Column("next_recreate_at", sa.DateTime(), nullable=True))
    op.add_column("manual_builds", sa.Column("last_recreate_at", sa.DateTime(), nullable=True))
    op.add_column("manual_builds", sa.Column("recreate_price_step_pct", sa.Float(), nullable=False, server_default="0.03"))
    op.add_column("manual_builds", sa.Column("traffic_band", sa.String(length=50), nullable=True))
    op.add_column("manual_builds", sa.Column("listed_at", sa.DateTime(), nullable=True))
    op.add_column("manual_builds", sa.Column("promoted_ad_rate_pct", sa.Float(), nullable=True))
    op.add_column("manual_builds", sa.Column("promoted_enabled", sa.Boolean(), nullable=False, server_default=sa.false()))
    op.add_column("manual_builds", sa.Column("markdown_event_opt_in", sa.Boolean(), nullable=False, server_default=sa.false()))


def downgrade() -> None:
    for column in reversed([
        "sold_comp_target", "active_range_ceiling", "price_floor",
        "price_last_recalculated_at", "price_floor_hit_review_needed",
        "demand_sold_count_90d", "demand_active_count", "demand_checked_at",
        "last_counter_offer_price", "counter_offer_round",
        "last_watcher_offer_sent_at", "recreate_cycle_count", "next_recreate_at",
        "last_recreate_at", "recreate_price_step_pct", "traffic_band",
        "listed_at", "promoted_ad_rate_pct", "promoted_enabled",
        "markdown_event_opt_in",
    ]):
        op.drop_column("manual_builds", column)
