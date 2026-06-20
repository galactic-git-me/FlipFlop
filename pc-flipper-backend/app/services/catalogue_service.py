"""
Catalogue layer service functions.

Called by:
  - Hourly scrape jobs (auto_publish_gems, check_freshness, update_prices)
  - Daily digest job (send_review_digest)
  - Admin API (approve_variant, reject_variant)
"""
from __future__ import annotations

import math
import logging
from datetime import datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.catalogue import PlaybookSlot, CatalogueVariant
from app.models.listing import Listing, Classification
from app.services.classifier import detect_component_category
from app.services.alerts import emit_alert

log = logging.getLogger(__name__)

# Maps classifier output → catalogue slot_type.
# Deliberately excludes motherboard, psu, accessory — not catalogue slot types.
_CATEGORY_TO_SLOT: dict[str, str] = {
    "cpu": "cpu",
    "gpu": "gpu",
    "ram": "ram",
    "ssd": "storage",
}

FRESH_WINDOW_HOURS = 2
MIN_GEM_SCORE = 40


def compute_display_price(scrape_price: float) -> float:
    """Return scrape_price × 1.15 rounded up to the nearest £5."""
    return math.ceil(scrape_price * 1.15 / 5) * 5


def determine_tier(gem_score: float, slot: PlaybookSlot) -> str:
    """Return 'budget', 'mid', or 'high' based on gem_score and slot score bands."""
    if gem_score >= slot.score_band_high[0]:
        return "high"
    if gem_score >= slot.score_band_mid[0]:
        return "mid"
    return "budget"


def infer_slot_type(title: str) -> str | None:
    """
    Derive catalogue slot_type from listing title using the existing classifier.
    Returns None for complete PCs, PSUs, motherboards, accessories.
    """
    raw = detect_component_category(title)
    return _CATEGORY_TO_SLOT.get(raw) if raw else None


async def auto_publish_gems(db: AsyncSession) -> int:
    """
    Step A: For every active gem listing, create a pending_review CatalogueVariant
    for each matching PlaybookSlot if one doesn't already exist.
    Returns the number of new variants created.
    """
    gem_classifications = (Classification.gem.value, Classification.amazing_gem.value)
    result = await db.execute(
        select(Listing).where(
            Listing.classification.in_(gem_classifications),
            Listing.gem_score >= MIN_GEM_SCORE,
        )
    )
    gem_listings = result.scalars().all()

    slots_result = await db.execute(select(PlaybookSlot))
    all_slots = slots_result.scalars().all()

    slots_by_type: dict[str, list[PlaybookSlot]] = {}
    for slot in all_slots:
        slots_by_type.setdefault(slot.slot_type, []).append(slot)

    existing_result = await db.execute(
        select(CatalogueVariant.listing_id, CatalogueVariant.slot_id)
    )
    existing_pairs = {(r.listing_id, r.slot_id) for r in existing_result}

    created = 0
    now = datetime.utcnow().isoformat()

    for listing in gem_listings:
        slot_type = infer_slot_type(listing.title)
        if not slot_type:
            continue
        for slot in slots_by_type.get(slot_type, []):
            if (listing.id, slot.id) in existing_pairs:
                continue
            tier = determine_tier(listing.gem_score, slot)
            variant = CatalogueVariant(
                listing_id=listing.id,
                slot_id=slot.id,
                status="pending_review",
                display_price=compute_display_price(listing.price),
                tier=tier,
                consecutive_misses=0,
                last_seen_at=now,
                auto_published_at=now,
            )
            db.add(variant)
            existing_pairs.add((listing.id, slot.id))
            created += 1

    await db.commit()
    log.info("auto_publish_gems: created %d new variants", created)
    return created


async def check_freshness(db: AsyncSession) -> int:
    """
    Step B: Increment consecutive_misses for variants whose listing hasn't been
    seen in the last FRESH_WINDOW_HOURS. Hide at 2 misses. Reinstate within 24h.
    Returns the number of variants hidden.
    """
    cutoff = datetime.utcnow() - timedelta(hours=FRESH_WINDOW_HOURS)
    reinstate_cutoff = datetime.utcnow() - timedelta(hours=24)

    result = await db.execute(
        select(CatalogueVariant, Listing)
        .join(Listing, CatalogueVariant.listing_id == Listing.id)
        .where(CatalogueVariant.status.in_(["active", "pending_review"]))
    )
    rows = result.all()

    hidden = 0
    newly_hidden_ids: set[int] = set()
    now = datetime.utcnow().isoformat()

    for variant, listing in rows:
        last_seen = listing.last_seen_at  # datetime object from DateTime column
        if last_seen and last_seen >= cutoff:
            variant.consecutive_misses = 0
            variant.last_seen_at = now
        else:
            variant.consecutive_misses += 1
            if variant.consecutive_misses >= 2:
                variant.status = "hidden"
                hidden += 1
                newly_hidden_ids.add(variant.id)

    q = (
        select(CatalogueVariant, Listing)
        .join(Listing, CatalogueVariant.listing_id == Listing.id)
        .where(CatalogueVariant.status == "hidden")
    )
    if newly_hidden_ids:
        q = q.where(CatalogueVariant.id.notin_(newly_hidden_ids))
    hidden_result = await db.execute(q)
    for variant, listing in hidden_result.all():
        last_seen = listing.last_seen_at  # datetime object
        if last_seen and last_seen >= reinstate_cutoff:
            variant.status = "active"
            variant.consecutive_misses = 0
            variant.last_seen_at = now

    await db.commit()
    log.info("check_freshness: hid %d variants", hidden)
    return hidden


async def update_prices(db: AsyncSession) -> int:
    """
    Step C: Recalculate display_price for all active variants from current listing price.
    Returns the number of variants updated.
    """
    result = await db.execute(
        select(CatalogueVariant, Listing)
        .join(Listing, CatalogueVariant.listing_id == Listing.id)
        .where(CatalogueVariant.status == "active")
    )
    rows = result.all()

    updated = 0
    for variant, listing in rows:
        new_price = compute_display_price(listing.price)
        if new_price != variant.display_price:
            variant.display_price = new_price
            updated += 1

    await db.commit()
    log.info("update_prices: updated %d variant prices", updated)
    return updated


async def send_review_digest(db: AsyncSession) -> None:
    """
    Step D: Emit an alert if any variants are pending review.
    Called once daily at 08:00 by the scheduler.
    """
    result = await db.execute(
        select(CatalogueVariant).where(CatalogueVariant.status == "pending_review")
    )
    pending = result.scalars().all()
    count = len(pending)
    if count > 0:
        await emit_alert(
            code="CATALOGUE_REVIEW_PENDING",
            source="catalogue_service",
            message=f"Catalogue review: {count} new variants awaiting approval",
            severity="info",
        )
        log.info("send_review_digest: emitted alert for %d pending variants", count)


async def approve_variant(
    db: AsyncSession, variant_id: int, reviewed_by: str = "admin"
) -> CatalogueVariant | None:
    result = await db.execute(
        select(CatalogueVariant).where(CatalogueVariant.id == variant_id)
    )
    variant = result.scalar_one_or_none()
    if not variant:
        return None
    variant.status = "active"
    variant.reviewed_at = datetime.utcnow().isoformat()
    variant.reviewed_by = reviewed_by
    variant.reject_reason = None
    await db.commit()
    await db.refresh(variant)
    return variant


async def reject_variant(
    db: AsyncSession, variant_id: int, reason: str, reviewed_by: str = "admin"
) -> CatalogueVariant | None:
    result = await db.execute(
        select(CatalogueVariant).where(CatalogueVariant.id == variant_id)
    )
    variant = result.scalar_one_or_none()
    if not variant:
        return None
    variant.status = "rejected"
    variant.reviewed_at = datetime.utcnow().isoformat()
    variant.reviewed_by = reviewed_by
    variant.reject_reason = reason
    await db.commit()
    await db.refresh(variant)
    return variant


async def run_catalogue_pipeline(db: AsyncSession) -> dict:
    """Runs Steps A+B+C in sequence. Called hourly by scheduler."""
    created = await auto_publish_gems(db)
    hidden = await check_freshness(db)
    updated = await update_prices(db)
    return {"variants_created": created, "variants_hidden": hidden, "prices_updated": updated}


async def run_catalogue_pipeline_job() -> dict:
    """Self-contained wrapper for scheduler — opens its own DB session."""
    from app.database import AsyncSessionLocal
    async with AsyncSessionLocal() as db:
        return await run_catalogue_pipeline(db)


async def run_catalogue_digest_job() -> None:
    """Self-contained wrapper for scheduler — opens its own DB session."""
    from app.database import AsyncSessionLocal
    async with AsyncSessionLocal() as db:
        await send_review_digest(db)
