"""Structured sourcing ingestion from FlipFlopXtension.

This API accepts extension-captured fields only. It never opens marketplace
URLs or retrieves marketplace HTML.
"""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from decimal import Decimal
from typing import Literal
from urllib.parse import urlsplit

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import require_operator
from app.database import get_db
from app.models.marketplace_sourcing import (
    MarketplaceBundle, MarketplaceBundleComponent, MarketplaceBundleVariant,
    MarketplaceListing, MarketplaceListingVariant, MarketplaceSupplierOffer,
)
from app.services.bundle_costs import allocate_bundle_cost

router = APIRouter(prefix="/gem-radar/sourcing", tags=["marketplace-sourcing"])
MARKET_HOSTS = {
    "ebay": ("ebay.co.uk",), "amazon": ("amazon.co.uk",),
    "overclockers": ("overclockers.co.uk",), "scan": ("scan.co.uk",),
    "awd_it": ("awd-it.co.uk",), "computer_orbit": ("computerorbit.com",),
    "bargain_hardware": ("bargainhardware.co.uk",), "newegg_uk": ("newegg.com",),
    "ebuyer": ("ebuyer.com",), "google_shopping": ("google.com", "google.co.uk"),
    "gamers_outlet": ("gamers-outlet.net",), "aliexpress": ("aliexpress.com",),
    "vinted": ("vinted.co.uk",),
}


class SourcingModel(BaseModel):
    model_config = ConfigDict(populate_by_name=True, alias_generator=lambda s: s.split("_")[0] + "".join(p.title() for p in s.split("_")[1:]))


class BundlePartInput(SourcingModel):
    canonical_part_key: str = Field(min_length=1, max_length=160)
    quantity: int = Field(default=1, ge=1, le=16)
    specifications: dict = Field(default_factory=dict)
    market_reference_price: Decimal | None = Field(default=None, gt=0)
    market_reference_currency: Literal["GBP"] = "GBP"
    reference_observed_at: datetime | None = None


class OfferVariantInput(SourcingModel):
    marketplace_variant_id: str | None = Field(default=None, max_length=160)
    selected_options: dict[str, str] = Field(default_factory=dict)
    specifications: dict = Field(default_factory=dict)
    item_price: Decimal = Field(ge=0, max_digits=12, decimal_places=2)
    currency: str = Field(min_length=3, max_length=3)
    shipping_price: Decimal | None = Field(default=None, ge=0, max_digits=12, decimal_places=2)
    tax_price: Decimal | None = Field(default=None, ge=0, max_digits=12, decimal_places=2)
    condition: str = Field(default="unknown", max_length=24)
    availability: Literal["available", "unavailable", "unknown"] = "unknown"
    verification_status: Literal["discovered", "needs_verification", "verified", "rejected", "stale", "unavailable"]
    observed_at: datetime
    source_url: str = Field(min_length=1, max_length=2000)
    evidence: dict = Field(default_factory=dict)
    bundle_type: str | None = Field(default=None, max_length=48)
    platform: str | None = Field(default=None, max_length=48)
    socket: str | None = Field(default=None, max_length=24)
    bundle_components: list[BundlePartInput] = Field(default_factory=list, max_length=16)

    @field_validator("source_url")
    @classmethod
    def secure_source_url(cls, value: str) -> str:
        parts = urlsplit(value)
        if parts.scheme != "https" or not parts.hostname or parts.username or parts.password:
            raise ValueError("variant source URL must be public HTTPS")
        return value

    @field_validator("currency")
    @classmethod
    def currency_uppercase(cls, value: str) -> str:
        value = value.upper()
        if value not in {"GBP", "EUR", "USD"}:
            raise ValueError("unsupported sourcing currency")
        return value


class SourcingListingInput(SourcingModel):
    marketplace: str
    marketplace_listing_id: str = Field(min_length=1, max_length=160)
    seller: str | None = Field(default=None, max_length=200)
    title: str = Field(min_length=1, max_length=1000)
    url: str = Field(min_length=1, max_length=2000)
    image_url: str | None = Field(default=None, max_length=2000)
    category: str | None = Field(default=None, max_length=64)
    discovered_at: datetime
    applied_filters: dict = Field(default_factory=dict)
    filter_confidence: Decimal = Field(default=Decimal("0"), ge=0, le=1)
    bundle_candidate: bool = False
    variants: list[OfferVariantInput] = Field(default_factory=list, max_length=100)

    @field_validator("marketplace")
    @classmethod
    def known_marketplace(cls, value: str) -> str:
        if value not in MARKET_HOSTS:
            raise ValueError("unsupported marketplace")
        return value

    @field_validator("url")
    @classmethod
    def public_marketplace_url(cls, value: str, info):
        parts = urlsplit(value)
        if parts.scheme != "https" or not parts.hostname or parts.username or parts.password:
            raise ValueError("marketplace listing URL must be public HTTPS")
        marketplace = info.data.get("marketplace")
        is_google_destination = marketplace == "google_shopping"
        if marketplace and not is_google_destination and not any(parts.hostname == host or parts.hostname.endswith("." + host) for host in MARKET_HOSTS[marketplace]):
            raise ValueError("listing URL host does not match marketplace")
        return value


class DiscoveryResultsInput(SourcingModel):
    job_id: str | None = Field(default=None, max_length=100)
    listings: list[SourcingListingInput] = Field(min_length=1, max_length=100)


class DiscoveryResultsResponse(SourcingModel):
    accepted: int
    variants: int
    offers: int
    bundles: int


def fingerprint(data: dict) -> str:
    normalized = json.dumps(data, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


@router.post("/results", response_model=DiscoveryResultsResponse)
async def ingest_extension_results(
    body: DiscoveryResultsInput,
    db: AsyncSession = Depends(get_db),
    _: None = Depends(require_operator),
) -> DiscoveryResultsResponse:
    """Validate and persist extension-submitted listings and selected offers."""
    now = datetime.now(timezone.utc)
    accepted = variant_count = offer_count = bundle_count = 0
    for entry in body.listings:
        listing = (await db.execute(select(MarketplaceListing).where(
            MarketplaceListing.marketplace == entry.marketplace,
            MarketplaceListing.marketplace_listing_id == entry.marketplace_listing_id,
        ).with_for_update())).scalar_one_or_none()
        if listing is None:
            listing = MarketplaceListing(
                marketplace=entry.marketplace, marketplace_listing_id=entry.marketplace_listing_id,
                seller=entry.seller, title=entry.title, url=entry.url, image_url=entry.image_url,
                category=entry.category, discovered_at=entry.discovered_at, last_seen_at=now,
                bundle_candidate=entry.bundle_candidate,
                source_evidence={"job_id": body.job_id, "applied_filters": entry.applied_filters,
                                 "filter_confidence": str(entry.filter_confidence), "source": "flipflopxtension"},
            )
            db.add(listing)
            await db.flush()
        else:
            listing.last_seen_at = now
            listing.seller = entry.seller or listing.seller
            listing.title = entry.title
            listing.url = entry.url
            listing.image_url = entry.image_url or listing.image_url
            listing.category = entry.category or listing.category
            listing.bundle_candidate = listing.bundle_candidate or entry.bundle_candidate
            listing.source_evidence = {**(listing.source_evidence or {}), "job_id": body.job_id,
                "applied_filters": entry.applied_filters, "filter_confidence": str(entry.filter_confidence),
                "source": "flipflopxtension"}

        if entry.bundle_candidate:
            candidate_bundle = (await db.execute(select(MarketplaceBundle).where(
                MarketplaceBundle.listing_id == listing.id,
            ).with_for_update())).scalar_one_or_none()
            if candidate_bundle is None:
                db.add(MarketplaceBundle(
                    listing_id=listing.id, bundle_type="unclassified",
                    verification_status="needs_verification", seller=entry.seller,
                ))
                bundle_count += 1

        for item in entry.variants:
            source_host = (urlsplit(item.source_url).hostname or "").lower()
            expected_hosts = MARKET_HOSTS[entry.marketplace]
            if entry.marketplace != "google_shopping" and not any(
                source_host == host or source_host.endswith("." + host) for host in expected_hosts
            ):
                raise HTTPException(422, "variant evidence URL host does not match marketplace")
            verification_status = item.verification_status
            if verification_status == "verified" and not (
                item.evidence.get("source_page_verified") is True
                and item.evidence.get("selected_price_stable") is True
                and (item.evidence.get("variant_controls_detected") is not True
                     or item.evidence.get("selected_options_capture_complete") is True)
            ):
                verification_status = "needs_verification"
            if item.bundle_components and verification_status == "verified" and item.evidence.get("bundle_contents_verified") is not True:
                verification_status = "needs_verification"
            opts = item.selected_options
            variant_fingerprint = fingerprint(opts)
            variant = (await db.execute(select(MarketplaceListingVariant).where(
                MarketplaceListingVariant.listing_id == listing.id,
                MarketplaceListingVariant.variant_fingerprint == variant_fingerprint,
            ).with_for_update())).scalar_one_or_none()
            verified_at = item.observed_at if verification_status == "verified" else None
            if variant is None:
                variant = MarketplaceListingVariant(
                    listing_id=listing.id, variant_fingerprint=variant_fingerprint,
                    marketplace_variant_id=item.marketplace_variant_id, selected_options=opts,
                    specifications=item.specifications, availability=item.availability,
                    verification_status=verification_status, verified_at=verified_at,
                    source_url=item.source_url,
                )
                db.add(variant)
                await db.flush()
                variant_count += 1
            else:
                variant.marketplace_variant_id = item.marketplace_variant_id or variant.marketplace_variant_id
                variant.specifications = item.specifications or variant.specifications
                variant.availability = item.availability
                variant.verification_status = verification_status
                variant.verified_at = verified_at or variant.verified_at
                variant.source_url = item.source_url

            landed = None
            if item.currency == "GBP" and item.shipping_price is not None:
                landed = item.item_price + item.shipping_price + (item.tax_price or Decimal("0"))
            offer_exists = (await db.execute(select(MarketplaceSupplierOffer.id).where(
                MarketplaceSupplierOffer.variant_id == variant.id,
                MarketplaceSupplierOffer.observed_at == item.observed_at,
            ))).scalar_one_or_none()
            if offer_exists is None:
                # Unverified search-card observations are retained as evidence
                # but cannot be treated as trusted price offers downstream.
                db.add(MarketplaceSupplierOffer(
                    variant_id=variant.id, item_price=item.item_price, currency=item.currency,
                    shipping_price=item.shipping_price, tax_price=item.tax_price, landed_cost=landed,
                    condition=item.condition, availability=item.availability,
                    verification_status=verification_status, observed_at=item.observed_at,
                    evidence={**item.evidence, "source": "flipflopxtension", "source_url": item.source_url},
                ))
                offer_count += 1

            if item.bundle_type:
                bundle_verification = verification_status
                if not item.bundle_components or item.evidence.get("bundle_contents_verified") is not True:
                    bundle_verification = "needs_verification"
                bundle = (await db.execute(select(MarketplaceBundle).where(
                    MarketplaceBundle.listing_id == listing.id,
                ).with_for_update())).scalar_one_or_none()
                if bundle is None:
                    bundle = MarketplaceBundle(
                        listing_id=listing.id, bundle_type=item.bundle_type, platform=item.platform,
                        socket=item.socket, verification_status=bundle_verification,
                        seller=entry.seller,
                    )
                    db.add(bundle)
                    await db.flush()
                    bundle_count += 1
                else:
                    bundle.bundle_type = item.bundle_type
                    bundle.platform = item.platform or bundle.platform
                    bundle.socket = item.socket or bundle.socket
                    bundle.verification_status = bundle_verification
                    bundle.seller = entry.seller or bundle.seller
                bundle_variant_fp = fingerprint({"options": opts, "marketplace_variant_id": item.marketplace_variant_id})
                bundle_variant = (await db.execute(select(MarketplaceBundleVariant).where(
                    MarketplaceBundleVariant.bundle_id == bundle.id,
                    MarketplaceBundleVariant.configuration_fingerprint == bundle_variant_fp,
                ).with_for_update())).scalar_one_or_none()
                if bundle_variant is None:
                    bundle_variant = MarketplaceBundleVariant(
                        bundle_id=bundle.id, configuration_fingerprint=bundle_variant_fp,
                        marketplace_variant_id=item.marketplace_variant_id, selected_configuration=opts,
                        total_price=item.item_price, shipping_price=item.shipping_price,
                        tax_price=item.tax_price,
                        landed_cost=landed if item.currency == "GBP" else None, currency=item.currency,
                        availability=item.availability, verification_status=bundle_verification,
                        verified_at=verified_at, evidence=item.evidence,
                    )
                    db.add(bundle_variant)
                    await db.flush()
                else:
                    bundle_variant.marketplace_variant_id = item.marketplace_variant_id or bundle_variant.marketplace_variant_id
                    bundle_variant.selected_configuration = opts
                    bundle_variant.total_price = item.item_price
                    bundle_variant.shipping_price = item.shipping_price
                    bundle_variant.tax_price = item.tax_price
                    bundle_variant.landed_cost = landed if item.currency == "GBP" else None
                    bundle_variant.currency = item.currency
                    bundle_variant.availability = item.availability
                    bundle_variant.verification_status = bundle_verification
                    bundle_variant.verified_at = verified_at or bundle_variant.verified_at
                    bundle_variant.evidence = item.evidence
                for part in item.bundle_components:
                    existing = (await db.execute(select(MarketplaceBundleComponent).where(
                        MarketplaceBundleComponent.bundle_variant_id == bundle_variant.id,
                        MarketplaceBundleComponent.canonical_part_key == part.canonical_part_key,
                    ))).scalar_one_or_none()
                    if existing is None:
                        db.add(MarketplaceBundleComponent(
                            bundle_variant_id=bundle_variant.id,
                            canonical_part_key=part.canonical_part_key,
                            quantity=part.quantity, specifications=part.specifications,
                            market_reference_price=part.market_reference_price,
                            reference_observed_at=part.reference_observed_at,
                        ))
                    else:
                        existing.quantity = part.quantity
                        existing.specifications = part.specifications
                        existing.market_reference_price = part.market_reference_price
                        existing.reference_observed_at = part.reference_observed_at
                # Proportional allocation is accounting metadata only. It is
                # emitted when every constituent has a current standalone
                # market reference and the extension verified the exact bundle.
                if bundle_verification == "verified" and item.evidence.get("bundle_contents_verified") is True:
                    refs = {
                        part.canonical_part_key: part.market_reference_price * part.quantity
                        for part in item.bundle_components if part.market_reference_price is not None
                    }
                    if len(refs) == len(item.bundle_components) and item.currency == "GBP":
                        allocation_total = landed if landed is not None else item.item_price
                        allocations = allocate_bundle_cost(allocation_total, refs)
                        for part in item.bundle_components:
                            component_row = (await db.execute(select(MarketplaceBundleComponent).where(
                                MarketplaceBundleComponent.bundle_variant_id == bundle_variant.id,
                                MarketplaceBundleComponent.canonical_part_key == part.canonical_part_key,
                            ))).scalar_one_or_none()
                            if component_row is not None:
                                component_row.attributed_cost = allocations[part.canonical_part_key]
                                component_row.allocation_method = "proportional_standalone_market"
                                component_row.allocation_confidence = Decimal("1.0000")
        accepted += 1
    await db.commit()
    return DiscoveryResultsResponse(accepted=accepted, variants=variant_count, offers=offer_count, bundles=bundle_count)


@router.get("/listings")
async def list_extension_listings(
    marketplace: str | None = None,
    bundle_only: bool = False,
    limit: int = 100,
    db: AsyncSession = Depends(get_db),
    _: None = Depends(require_operator),
):
    """Admin-facing evidence feed; only verified variants are trusted offers."""
    if not 1 <= limit <= 500:
        raise HTTPException(422, "limit must be between 1 and 500")
    query = select(MarketplaceListing).order_by(MarketplaceListing.last_seen_at.desc()).limit(limit)
    if marketplace:
        if marketplace not in MARKET_HOSTS:
            raise HTTPException(422, "unsupported marketplace")
        query = query.where(MarketplaceListing.marketplace == marketplace)
    if bundle_only:
        query = query.where(MarketplaceListing.bundle_candidate.is_(True))
    rows = (await db.execute(query)).scalars().all()
    return [{
        "id": row.id, "marketplace": row.marketplace, "marketplace_listing_id": row.marketplace_listing_id,
        "seller": row.seller, "title": row.title, "url": row.url, "image_url": row.image_url,
        "category": row.category, "bundle_candidate": row.bundle_candidate,
        "source_evidence": row.source_evidence, "discovered_at": row.discovered_at,
        "last_seen_at": row.last_seen_at,
    } for row in rows]


@router.get("/listings/{listing_id}")
async def get_extension_listing(
    listing_id: int,
    db: AsyncSession = Depends(get_db),
    _: None = Depends(require_operator),
):
    listing = await db.get(MarketplaceListing, listing_id)
    if listing is None:
        raise HTTPException(404, "sourcing listing not found")
    variants = (await db.execute(select(MarketplaceListingVariant).where(
        MarketplaceListingVariant.listing_id == listing.id,
    ).order_by(MarketplaceListingVariant.id))).scalars().all()
    variant_ids = [variant.id for variant in variants]
    offers = (await db.execute(select(MarketplaceSupplierOffer).where(
        MarketplaceSupplierOffer.variant_id.in_(variant_ids) if variant_ids else False,
    ).order_by(MarketplaceSupplierOffer.observed_at.desc()))).scalars().all()
    bundles = (await db.execute(select(MarketplaceBundle).where(
        MarketplaceBundle.listing_id == listing.id,
    ))).scalars().all()
    bundle_ids = [bundle.id for bundle in bundles]
    bundle_variants = (await db.execute(select(MarketplaceBundleVariant).where(
        MarketplaceBundleVariant.bundle_id.in_(bundle_ids) if bundle_ids else False,
    ))).scalars().all()
    bundle_variant_ids = [variant.id for variant in bundle_variants]
    components = (await db.execute(select(MarketplaceBundleComponent).where(
        MarketplaceBundleComponent.bundle_variant_id.in_(bundle_variant_ids) if bundle_variant_ids else False,
    ))).scalars().all()
    components_by_variant: dict[int, list[dict]] = {}
    for component in components:
        components_by_variant.setdefault(component.bundle_variant_id, []).append({
            "canonical_part_key": component.canonical_part_key, "quantity": component.quantity,
            "specifications": component.specifications, "attributed_cost": component.attributed_cost,
            "market_reference_price": component.market_reference_price,
            "reference_observed_at": component.reference_observed_at,
            "allocation_method": component.allocation_method,
            "allocation_confidence": component.allocation_confidence,
        })
    return {
        "id": listing.id, "marketplace": listing.marketplace,
        "marketplace_listing_id": listing.marketplace_listing_id, "seller": listing.seller,
        "title": listing.title, "url": listing.url, "image_url": listing.image_url,
        "category": listing.category, "bundle_candidate": listing.bundle_candidate,
        "source_evidence": listing.source_evidence, "discovered_at": listing.discovered_at,
        "last_seen_at": listing.last_seen_at,
        "variants": [{
            "id": variant.id, "marketplace_variant_id": variant.marketplace_variant_id,
            "selected_options": variant.selected_options, "specifications": variant.specifications,
            "availability": variant.availability, "verification_status": variant.verification_status,
            "verified_at": variant.verified_at, "offers": [{
                "id": offer.id, "canonical_part_key": offer.canonical_part_key,
                "item_price": offer.item_price, "currency": offer.currency,
                "shipping_price": offer.shipping_price, "tax_price": offer.tax_price,
                "landed_cost": offer.landed_cost, "condition": offer.condition,
                "availability": offer.availability, "verification_status": offer.verification_status,
                "observed_at": offer.observed_at, "evidence": offer.evidence,
            } for offer in offers if offer.variant_id == variant.id],
        } for variant in variants],
        "bundles": [{
            "id": bundle.id, "bundle_type": bundle.bundle_type, "platform": bundle.platform,
            "socket": bundle.socket, "seller": bundle.seller,
            "verification_status": bundle.verification_status,
            "variants": [{
                "id": variant.id, "selected_configuration": variant.selected_configuration,
                "total_price": variant.total_price, "currency": variant.currency,
                "shipping_price": variant.shipping_price, "tax_price": variant.tax_price,
                "landed_cost": variant.landed_cost, "availability": variant.availability,
                "verification_status": variant.verification_status, "verified_at": variant.verified_at,
                "components": components_by_variant.get(variant.id, []),
            } for variant in bundle_variants if variant.bundle_id == bundle.id],
        } for bundle in bundles],
    }
