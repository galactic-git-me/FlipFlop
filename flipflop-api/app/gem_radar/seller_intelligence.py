"""Seller intelligence aggregation (PRD §25). Every scored listing updates
the seller's rolling profile; cancellation_count/issue_count stay at 0 (no
fabricated risk signal) until a reconciliation source exists to populate
them — see app/models/gem_radar_seller_profile.py docstring.
"""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.gem_radar_seller_profile import GemRadarSellerProfile
from app.gem_radar.schemas import Classification, ExtractedListing, SellerIntelligence


async def upsert_seller_profile(
    db: AsyncSession, listing: ExtractedListing, classification: Classification
) -> GemRadarSellerProfile | None:
    if not listing.seller:
        return None

    result = await db.execute(select(GemRadarSellerProfile).where(GemRadarSellerProfile.seller_name == listing.seller))
    profile = result.scalar_one_or_none()

    if profile is None:
        # Column-level defaults (default=0) only apply at INSERT/flush time,
        # not to the in-memory object immediately after construction — and
        # this function does `+= 1` arithmetic on that object before any
        # flush happens, so every counter must be seeded explicitly here or
        # it stays None and the increment below raises a TypeError.
        profile = GemRadarSellerProfile(
            seller_name=listing.seller,
            feedback_percent=listing.seller_feedback_percent,
            feedback_count=listing.seller_feedback_count,
            observed_listings_count=0,
            historical_gem_count=0,
            historical_super_gem_count=0,
            historical_purchase_count=0,
            cancellation_count=0,
            issue_count=0,
            first_seen_at=datetime.now(timezone.utc).replace(tzinfo=None),
            last_seen_at=datetime.now(timezone.utc).replace(tzinfo=None),
        )
        db.add(profile)

    profile.observed_listings_count += 1
    if classification == "SUPER_GEM":
        profile.historical_super_gem_count += 1
    if classification in ("SUPER_GEM", "GEM"):
        profile.historical_gem_count += 1
    # Feedback numbers are only ever shown on eBay item pages, not search
    # cards (see content script comment) — only overwrite when we actually
    # have a fresh value, never blank out a previously-known figure.
    if listing.seller_feedback_percent is not None:
        profile.feedback_percent = listing.seller_feedback_percent
    if listing.seller_feedback_count is not None:
        profile.feedback_count = listing.seller_feedback_count
    profile.last_seen_at = datetime.now(timezone.utc).replace(tzinfo=None)

    await db.commit()
    await db.refresh(profile)
    return profile


async def increment_purchase_count(db: AsyncSession, seller_name: str) -> None:
    """Called from purchases.py on a successful Bought It — historical
    purchase count is a purchase-workflow signal, not a scan-time one.
    """
    result = await db.execute(select(GemRadarSellerProfile).where(GemRadarSellerProfile.seller_name == seller_name))
    profile = result.scalar_one_or_none()
    if profile is None:
        return
    profile.historical_purchase_count += 1
    await db.commit()


async def get_seller_profile(db: AsyncSession, seller_name: str) -> SellerIntelligence | None:
    result = await db.execute(select(GemRadarSellerProfile).where(GemRadarSellerProfile.seller_name == seller_name))
    profile = result.scalar_one_or_none()
    if profile is None:
        return None
    return SellerIntelligence(
        sellerName=profile.seller_name,
        feedbackPercent=profile.feedback_percent,
        feedbackCount=profile.feedback_count,
        sellerType=profile.seller_type,
        observedListings=profile.observed_listings_count,
        historicalGemCount=profile.historical_gem_count,
        historicalSuperGemCount=profile.historical_super_gem_count,
        historicalPurchaseCount=profile.historical_purchase_count,
        cancellationCount=profile.cancellation_count,
        issueCount=profile.issue_count,
    )
