"""Structured listings, verified variants, offers, and multi-part bundles.

All marketplace-originated values in these tables are submitted by the
FlipFlop browser extension. Backend code validates and stores evidence only.
"""
from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import (
    Boolean, DateTime, ForeignKey, Integer, JSON, Numeric, String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class MarketplaceListing(Base):
    __tablename__ = "marketplace_sourcing_listings"
    __table_args__ = (UniqueConstraint("marketplace", "marketplace_listing_id", name="uq_marketplace_listing_identity"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    marketplace: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    marketplace_listing_id: Mapped[str] = mapped_column(String(160), nullable=False)
    seller: Mapped[str | None] = mapped_column(String(200))
    title: Mapped[str] = mapped_column(String(1000), nullable=False)
    url: Mapped[str] = mapped_column(String(2000), nullable=False)
    image_url: Mapped[str | None] = mapped_column(String(2000))
    category: Mapped[str | None] = mapped_column(String(64), index=True)
    discovered_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now)
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now)
    bundle_candidate: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, index=True)
    source_evidence: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)


class MarketplaceListingVariant(Base):
    __tablename__ = "marketplace_listing_variants"
    __table_args__ = (UniqueConstraint("listing_id", "variant_fingerprint", name="uq_marketplace_variant_identity"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    listing_id: Mapped[int] = mapped_column(ForeignKey("marketplace_sourcing_listings.id", ondelete="CASCADE"), nullable=False, index=True)
    variant_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    marketplace_variant_id: Mapped[str | None] = mapped_column(String(160))
    selected_options: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    specifications: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    availability: Mapped[str] = mapped_column(String(24), nullable=False, default="unknown")
    verification_status: Mapped[str] = mapped_column(String(24), nullable=False, default="discovered", index=True)
    verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    source_url: Mapped[str] = mapped_column(String(2000), nullable=False)


class MarketplaceSupplierOffer(Base):
    __tablename__ = "marketplace_supplier_offers"
    __table_args__ = (UniqueConstraint("variant_id", "observed_at", name="uq_marketplace_offer_observation"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    variant_id: Mapped[int] = mapped_column(ForeignKey("marketplace_listing_variants.id", ondelete="CASCADE"), nullable=False, index=True)
    canonical_part_key: Mapped[str | None] = mapped_column(String(160), index=True)
    item_price: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    shipping_price: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))
    tax_price: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))
    landed_cost: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))
    condition: Mapped[str] = mapped_column(String(24), nullable=False, default="unknown")
    availability: Mapped[str] = mapped_column(String(24), nullable=False, default="unknown")
    verification_status: Mapped[str] = mapped_column(String(24), nullable=False, index=True)
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    evidence: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)


class MarketplaceBundle(Base):
    __tablename__ = "marketplace_bundles"
    __table_args__ = (UniqueConstraint("listing_id", name="uq_marketplace_bundle_listing"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    listing_id: Mapped[int] = mapped_column(ForeignKey("marketplace_sourcing_listings.id", ondelete="CASCADE"), nullable=False)
    bundle_type: Mapped[str] = mapped_column(String(48), nullable=False, index=True)
    platform: Mapped[str | None] = mapped_column(String(48), index=True)
    socket: Mapped[str | None] = mapped_column(String(24), index=True)
    verification_status: Mapped[str] = mapped_column(String(24), nullable=False, default="needs_verification", index=True)
    seller: Mapped[str | None] = mapped_column(String(200))


class MarketplaceBundleVariant(Base):
    __tablename__ = "marketplace_bundle_variants"
    __table_args__ = (UniqueConstraint("bundle_id", "configuration_fingerprint", name="uq_marketplace_bundle_variant"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    bundle_id: Mapped[int] = mapped_column(ForeignKey("marketplace_bundles.id", ondelete="CASCADE"), nullable=False, index=True)
    configuration_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    marketplace_variant_id: Mapped[str | None] = mapped_column(String(160))
    selected_configuration: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    total_price: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    shipping_price: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))
    tax_price: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))
    landed_cost: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    availability: Mapped[str] = mapped_column(String(24), nullable=False, default="unknown")
    verification_status: Mapped[str] = mapped_column(String(24), nullable=False, index=True)
    verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    evidence: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)


class MarketplaceBundleComponent(Base):
    __tablename__ = "marketplace_bundle_components"
    __table_args__ = (UniqueConstraint("bundle_variant_id", "canonical_part_key", name="uq_marketplace_bundle_component"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    bundle_variant_id: Mapped[int] = mapped_column(ForeignKey("marketplace_bundle_variants.id", ondelete="CASCADE"), nullable=False, index=True)
    canonical_part_key: Mapped[str] = mapped_column(String(160), nullable=False, index=True)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    specifications: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    market_reference_price: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))
    reference_observed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    attributed_cost: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))
    allocation_method: Mapped[str | None] = mapped_column(String(32))
    allocation_confidence: Mapped[Decimal | None] = mapped_column(Numeric(5, 4))
