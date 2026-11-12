"""Add extension-submitted marketplace variants, offers, and bundle data.

Revision ID: 20261113_0001
Revises: 20261112_0002
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20261113_0001"
down_revision: Union[str, None] = "20261112_0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "marketplace_sourcing_listings",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("marketplace", sa.String(32), nullable=False),
        sa.Column("marketplace_listing_id", sa.String(160), nullable=False),
        sa.Column("seller", sa.String(200)), sa.Column("title", sa.String(1000), nullable=False),
        sa.Column("url", sa.String(2000), nullable=False), sa.Column("image_url", sa.String(2000)),
        sa.Column("category", sa.String(64)), sa.Column("discovered_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("bundle_candidate", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("source_evidence", sa.JSON(), nullable=False),
        sa.UniqueConstraint("marketplace", "marketplace_listing_id", name="uq_marketplace_listing_identity"),
    )
    op.create_index("ix_marketplace_sourcing_listings_marketplace", "marketplace_sourcing_listings", ["marketplace"])
    op.create_index("ix_marketplace_sourcing_listings_category", "marketplace_sourcing_listings", ["category"])
    op.create_index("ix_marketplace_sourcing_listings_bundle_candidate", "marketplace_sourcing_listings", ["bundle_candidate"])

    op.create_table(
        "marketplace_listing_variants",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("listing_id", sa.Integer(), sa.ForeignKey("marketplace_sourcing_listings.id", ondelete="CASCADE"), nullable=False),
        sa.Column("variant_fingerprint", sa.String(64), nullable=False),
        sa.Column("marketplace_variant_id", sa.String(160)), sa.Column("selected_options", sa.JSON(), nullable=False),
        sa.Column("specifications", sa.JSON(), nullable=False), sa.Column("availability", sa.String(24), nullable=False),
        sa.Column("verification_status", sa.String(24), nullable=False), sa.Column("verified_at", sa.DateTime(timezone=True)),
        sa.Column("source_url", sa.String(2000), nullable=False),
        sa.UniqueConstraint("listing_id", "variant_fingerprint", name="uq_marketplace_variant_identity"),
    )
    op.create_index("ix_marketplace_listing_variants_listing_id", "marketplace_listing_variants", ["listing_id"])
    op.create_index("ix_marketplace_listing_variants_verification_status", "marketplace_listing_variants", ["verification_status"])

    op.create_table(
        "marketplace_supplier_offers",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("variant_id", sa.Integer(), sa.ForeignKey("marketplace_listing_variants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("canonical_part_key", sa.String(160)), sa.Column("item_price", sa.Numeric(12, 2), nullable=False),
        sa.Column("currency", sa.String(3), nullable=False), sa.Column("shipping_price", sa.Numeric(12, 2)),
        sa.Column("tax_price", sa.Numeric(12, 2)), sa.Column("landed_cost", sa.Numeric(12, 2)),
        sa.Column("condition", sa.String(24), nullable=False), sa.Column("availability", sa.String(24), nullable=False),
        sa.Column("verification_status", sa.String(24), nullable=False),
        sa.Column("observed_at", sa.DateTime(timezone=True), nullable=False), sa.Column("evidence", sa.JSON(), nullable=False),
        sa.UniqueConstraint("variant_id", "observed_at", name="uq_marketplace_offer_observation"),
    )
    op.create_index("ix_marketplace_supplier_offers_variant_id", "marketplace_supplier_offers", ["variant_id"])
    op.create_index("ix_marketplace_supplier_offers_canonical_part_key", "marketplace_supplier_offers", ["canonical_part_key"])
    op.create_index("ix_marketplace_supplier_offers_verification_status", "marketplace_supplier_offers", ["verification_status"])

    op.create_table(
        "marketplace_bundles",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("listing_id", sa.Integer(), sa.ForeignKey("marketplace_sourcing_listings.id", ondelete="CASCADE"), nullable=False),
        sa.Column("bundle_type", sa.String(48), nullable=False), sa.Column("platform", sa.String(48)),
        sa.Column("socket", sa.String(24)), sa.Column("verification_status", sa.String(24), nullable=False),
        sa.Column("seller", sa.String(200)), sa.UniqueConstraint("listing_id", name="uq_marketplace_bundle_listing"),
    )
    op.create_index("ix_marketplace_bundles_bundle_type", "marketplace_bundles", ["bundle_type"])
    op.create_index("ix_marketplace_bundles_platform", "marketplace_bundles", ["platform"])
    op.create_index("ix_marketplace_bundles_socket", "marketplace_bundles", ["socket"])
    op.create_index("ix_marketplace_bundles_verification_status", "marketplace_bundles", ["verification_status"])

    op.create_table(
        "marketplace_bundle_variants",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("bundle_id", sa.Integer(), sa.ForeignKey("marketplace_bundles.id", ondelete="CASCADE"), nullable=False),
        sa.Column("configuration_fingerprint", sa.String(64), nullable=False),
        sa.Column("marketplace_variant_id", sa.String(160)), sa.Column("selected_configuration", sa.JSON(), nullable=False),
        sa.Column("total_price", sa.Numeric(12, 2), nullable=False), sa.Column("shipping_price", sa.Numeric(12, 2)),
        sa.Column("tax_price", sa.Numeric(12, 2)), sa.Column("landed_cost", sa.Numeric(12, 2)),
        sa.Column("currency", sa.String(3), nullable=False), sa.Column("availability", sa.String(24), nullable=False),
        sa.Column("verification_status", sa.String(24), nullable=False), sa.Column("verified_at", sa.DateTime(timezone=True)),
        sa.Column("evidence", sa.JSON(), nullable=False),
        sa.UniqueConstraint("bundle_id", "configuration_fingerprint", name="uq_marketplace_bundle_variant"),
    )
    op.create_index("ix_marketplace_bundle_variants_bundle_id", "marketplace_bundle_variants", ["bundle_id"])
    op.create_index("ix_marketplace_bundle_variants_verification_status", "marketplace_bundle_variants", ["verification_status"])

    op.create_table(
        "marketplace_bundle_components",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("bundle_variant_id", sa.Integer(), sa.ForeignKey("marketplace_bundle_variants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("canonical_part_key", sa.String(160), nullable=False), sa.Column("quantity", sa.Integer(), nullable=False),
        sa.Column("specifications", sa.JSON(), nullable=False), sa.Column("attributed_cost", sa.Numeric(12, 2)),
        sa.Column("allocation_method", sa.String(32)), sa.Column("allocation_confidence", sa.Numeric(5, 4)),
        sa.UniqueConstraint("bundle_variant_id", "canonical_part_key", name="uq_marketplace_bundle_component"),
    )
    op.create_index("ix_marketplace_bundle_components_bundle_variant_id", "marketplace_bundle_components", ["bundle_variant_id"])
    op.create_index("ix_marketplace_bundle_components_canonical_part_key", "marketplace_bundle_components", ["canonical_part_key"])


def downgrade() -> None:
    op.drop_table("marketplace_bundle_components")
    op.drop_table("marketplace_bundle_variants")
    op.drop_table("marketplace_bundles")
    op.drop_table("marketplace_supplier_offers")
    op.drop_table("marketplace_listing_variants")
    op.drop_table("marketplace_sourcing_listings")
