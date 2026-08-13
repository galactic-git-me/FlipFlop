"""Add Gem Radar "Bought It" provenance fields to inventory

Extends the existing InventoryItem table rather than creating a competing
purchase table (see gem-radar-extension/docs/ARCHITECTURE_GAP_ANALYSIS.md
Slice X5). Adds marketplace/listing provenance, purchase/reconciliation
status, and a partial unique index for duplicate-purchase protection
(PRD §26.4 — do not create duplicate inventory from the same listing twice).

Revision ID: 20260706_0014
Revises: a1b2c3d4e5f6
Create Date: 2026-07-06
"""
from alembic import op
import sqlalchemy as sa

revision = "20260706_0014"
down_revision = "a1b2c3d4e5f6"
depends_on = None


def upgrade():
    op.add_column("inventory", sa.Column("marketplace", sa.String(length=50), nullable=True))
    op.add_column("inventory", sa.Column("listing_id", sa.String(length=255), nullable=True))
    op.add_column("inventory", sa.Column("listing_url", sa.String(length=1000), nullable=True))
    op.add_column("inventory", sa.Column("seller_name", sa.String(length=200), nullable=True))
    op.add_column(
        "inventory",
        sa.Column("purchase_status", sa.String(length=32), server_default="MANUAL", nullable=False),
    )
    op.add_column(
        "inventory",
        sa.Column("reconciliation_status", sa.String(length=32), server_default="NOT_APPLICABLE", nullable=False),
    )

    # Partial unique index: two Bought It submissions for the same
    # marketplace+listing_id must not create two inventory rows. NULL
    # listing_id (manual/non-extension inventory entries) is unrestricted.
    op.create_index(
        "ix_inventory_marketplace_listing_unique",
        "inventory",
        ["marketplace", "listing_id"],
        unique=True,
        postgresql_where=sa.text("listing_id IS NOT NULL"),
        sqlite_where=sa.text("listing_id IS NOT NULL"),
    )


def downgrade():
    op.drop_index("ix_inventory_marketplace_listing_unique", table_name="inventory")
    op.drop_column("inventory", "reconciliation_status")
    op.drop_column("inventory", "purchase_status")
    op.drop_column("inventory", "seller_name")
    op.drop_column("inventory", "listing_url")
    op.drop_column("inventory", "listing_id")
    op.drop_column("inventory", "marketplace")
