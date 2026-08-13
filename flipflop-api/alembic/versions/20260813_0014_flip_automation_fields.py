"""Add pricing/offers/recreate-cycle/scheduler automation fields to flips table

Revision ID: 20260813_0014
Revises: a1b2c3d4e5f6
Create Date: 2026-08-13
"""
from alembic import op
import sqlalchemy as sa

revision = "20260813_0014"
down_revision = "a1b2c3d4e5f6"
depends_on = None


def upgrade():
    # Pricing & offers engine
    op.add_column('flips', sa.Column('min_offer_price', sa.Float(), nullable=True))
    op.add_column('flips', sa.Column('offers_enabled', sa.Boolean(), nullable=False, server_default=sa.true()))
    op.add_column('flips', sa.Column('listing_price', sa.Float(), nullable=True))
    op.add_column('flips', sa.Column('sold_comp_target', sa.Float(), nullable=True))
    op.add_column('flips', sa.Column('active_range_ceiling', sa.Float(), nullable=True))
    op.add_column('flips', sa.Column('price_floor', sa.Float(), nullable=True))
    op.add_column('flips', sa.Column('price_last_recalculated_at', sa.DateTime(), nullable=True))
    op.add_column('flips', sa.Column('price_floor_hit_review_needed', sa.Boolean(), nullable=False, server_default=sa.false()))
    op.add_column('flips', sa.Column('last_counter_offer_price', sa.Float(), nullable=True))
    op.add_column('flips', sa.Column('counter_offer_round', sa.Integer(), nullable=False, server_default='0'))
    op.add_column('flips', sa.Column('last_watcher_offer_sent_at', sa.DateTime(), nullable=True))

    # Demand check
    op.add_column('flips', sa.Column('demand_sold_count_90d', sa.Integer(), nullable=True))
    op.add_column('flips', sa.Column('demand_active_count', sa.Integer(), nullable=True))
    op.add_column('flips', sa.Column('demand_checked_at', sa.DateTime(), nullable=True))

    # Freshness / recreate cycle
    op.add_column('flips', sa.Column('recreate_cycle_count', sa.Integer(), nullable=False, server_default='0'))
    op.add_column('flips', sa.Column('next_recreate_at', sa.DateTime(), nullable=True))
    op.add_column('flips', sa.Column('last_recreate_at', sa.DateTime(), nullable=True))
    op.add_column('flips', sa.Column('recreate_price_step_pct', sa.Float(), nullable=False, server_default='0.03'))

    # Deferred-listing scheduler
    op.add_column('flips', sa.Column('deferred_publish_at', sa.DateTime(), nullable=True))
    op.add_column('flips', sa.Column('traffic_band', sa.String(50), nullable=True))
    op.add_column('flips', sa.Column('listed_at', sa.DateTime(), nullable=True))

    # Paid visibility
    op.add_column('flips', sa.Column('promoted_ad_rate_pct', sa.Float(), nullable=True))
    op.add_column('flips', sa.Column('promoted_enabled', sa.Boolean(), nullable=False, server_default=sa.false()))
    op.add_column('flips', sa.Column('markdown_event_opt_in', sa.Boolean(), nullable=False, server_default=sa.false()))


def downgrade():
    for col in [
        'markdown_event_opt_in', 'promoted_enabled', 'promoted_ad_rate_pct',
        'listed_at', 'traffic_band', 'deferred_publish_at',
        'recreate_price_step_pct', 'last_recreate_at', 'next_recreate_at', 'recreate_cycle_count',
        'demand_checked_at', 'demand_active_count', 'demand_sold_count_90d',
        'last_watcher_offer_sent_at', 'counter_offer_round', 'last_counter_offer_price',
        'price_floor_hit_review_needed', 'price_last_recalculated_at', 'price_floor',
        'active_range_ceiling', 'sold_comp_target', 'listing_price', 'offers_enabled', 'min_offer_price',
    ]:
        op.drop_column('flips', col)
