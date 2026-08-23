"""Add listing proliferator tables for Phase 2 (F2.2)

Enables multi-channel listing with dry-run validation and inventory reservation.
- channel_listings: Track listings across eBay and Storefront
- inventory_reservations: Prevent overselling
- listing_publish_events: Audit trail

Revision ID: 20260823_0006
Revises: 20260823_0005
Create Date: 2026-08-23
"""
from alembic import op
import sqlalchemy as sa


revision = "20260823_0006"
down_revision = "20260823_0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Channel listings: one per channel per build
    op.create_table(
        "channel_listings",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("manual_build_id", sa.Integer(), nullable=False),
        sa.Column("channel", sa.String(30), nullable=False),  # ebay, storefront, etc.
        sa.Column("status", sa.String(30), nullable=False, server_default="draft"),  # draft, scheduled, published, withdrawn
        sa.Column("external_listing_id", sa.String(100), nullable=True),  # eBay item ID or Storefront SKU
        sa.Column("published_at", sa.DateTime(), nullable=True),
        sa.Column("withdrawn_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now(), onupdate=sa.func.now()),
        sa.ForeignKeyConstraint(["manual_build_id"], ["manual_builds.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.Index("ix_channel_listings_manual_build_id", "manual_build_id"),
        sa.Index("ix_channel_listings_channel", "channel"),
        sa.Index("ix_channel_listings_status", "status"),
    )

    # Inventory reservations: prevent overselling across channels
    op.create_table(
        "inventory_reservations",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("manual_build_id", sa.Integer(), nullable=False),
        sa.Column("channel", sa.String(30), nullable=False),  # which channel reserved
        sa.Column("quantity_reserved", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("reserved_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("released_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["manual_build_id"], ["manual_builds.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.Index("ix_inventory_reservations_manual_build_id", "manual_build_id"),
        sa.Index("ix_inventory_reservations_released_at", "released_at"),
    )

    # Publishing audit trail
    op.create_table(
        "listing_publish_events",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("channel_listing_id", sa.Integer(), nullable=False),
        sa.Column("event_type", sa.String(50), nullable=False),  # published, withdrawn, dry_run, validation_failed
        sa.Column("message", sa.String(500), nullable=True),
        sa.Column("metadata", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["channel_listing_id"], ["channel_listings.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.Index("ix_listing_publish_events_channel_listing_id", "channel_listing_id"),
        sa.Index("ix_listing_publish_events_event_type", "event_type"),
    )


def downgrade() -> None:
    op.drop_table("listing_publish_events")
    op.drop_table("inventory_reservations")
    op.drop_table("channel_listings")
