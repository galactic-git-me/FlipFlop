"""Consolidate CPK pricing and rescore all listings with working pipeline."""
from __future__ import annotations

import asyncio
import sys
from pathlib import Path
from datetime import datetime, timezone

sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import text
from app.database import AsyncSessionLocal
from app.gem_radar.cpk_consolidation import consolidate_cpk_pricing
from app.gem_radar.pipeline import score_listing
from app.gem_radar.adapters.sold_comps import UnavailableSoldCompsAdapter
from app.gem_radar.adapters.amazon_price import UnavailableAmazonPriceAdapter
from app.models.gem_radar_scored_listing import GemRadarScoredListing
from app.gem_radar.schemas import ExtractedListing

import structlog

log = structlog.get_logger(__name__)


async def consolidate_and_rescore():
    """Consolidate CPK pricing and rescore all listings."""
    async with AsyncSessionLocal() as db:
        # Step 1: Consolidate CPK pricing (groups by CPK and aggregates prices)
        print("=" * 80)
        print("Step 1: Consolidating CPK pricing...")
        print("=" * 80)

        await consolidate_cpk_pricing(db)

        # Step 2: Clear old scores and rescore with working CPK pipeline
        print()
        print("=" * 80)
        print("Step 2: Rescoring all listings with CPK-enabled pipeline...")
        print("=" * 80)
        print()

        # Get all observation records
        query = """
        SELECT
            lo.listing_id, lo.title, lo.seller_name, lo.image_url,
            lo.condition_normalised as condition, lo.item_price, lo.postage_price,
            lo.delivered_price, lo.listing_type, lo.best_offer_enabled,
            lo.bid_count, lo.source, lo.observed_at
        FROM gem_radar_listing_observations lo
        ORDER BY lo.observed_at DESC
        """

        result = await db.execute(text(query))
        listings = result.fetchall()

        if not listings:
            print("No listings to score.")
            return

        total = len(listings)
        print(f"Scoring {total} observations...")
        print()

        priced_count = 0
        cpk_priced = 0
        gem = 0
        super_gem = 0
        start_time = datetime.now(timezone.utc)

        # Get count of CPK-extracted listings
        cpk_result = await db.execute(text('SELECT COUNT(*) FROM gem_radar_scored_listings WHERE cpk IS NOT NULL'))
        cpk_total = cpk_result.scalar()
        print(f"Note: {cpk_total} listings already have CPK extracted")
        print()

        sold_adapter = UnavailableSoldCompsAdapter()
        amazon_adapter = UnavailableAmazonPriceAdapter()

        # Clear old scores
        await db.execute(text("DELETE FROM gem_radar_scored_listings"))
        await db.commit()

        for i, row in enumerate(listings, 1):
            try:
                listing_dict = {
                    "listingId": row[0],
                    "url": f"https://ebay.co.uk/itm/{row[0]}",
                    "title": row[1],
                    "seller": row[2],
                    "sellerFeedbackPercent": None,
                    "sellerFeedbackCount": None,
                    "conditionRaw": row[4],
                    "conditionNormalised": row[4],
                    "itemPrice": row[5],
                    "postagePrice": row[6],
                    "currentDeliveredPrice": row[7],
                    "listingType": row[8],
                    "bestOfferEnabled": row[9],
                    "bidCount": row[10],
                    "auctionEndAt": None,
                    "imageUrl": row[3],
                    "sponsored": False,
                    "extractedAt": row[12].replace(tzinfo=timezone.utc) if row[12] else datetime.now(timezone.utc),
                }
                listing = ExtractedListing(**listing_dict)

                # Score with pipeline - will internally look up and use CPK pricing if available
                scored = await score_listing(
                    db, listing, rank=i, sold_adapter=sold_adapter,
                    amazon_adapter=amazon_adapter, deep_research=False
                )

                db_row = GemRadarScoredListing(
                    listing_id=scored.listing.listing_id,
                    search_run_id="cpk-rescore",
                    source=row[11],
                    url=listing.url,
                    title=scored.listing.title,
                    seller_name=scored.listing.seller,
                    image_url=scored.listing.image_url,
                    condition=scored.listing.condition_normalised,
                    category=scored.identity.category,
                    canonical_model_id=scored.identity.model_canonical,
                    actual_listing_price=scored.listing.item_price,
                    postage_price=scored.listing.postage_price,
                    delivered_price=scored.listing.current_delivered_price,
                    market_new_price=scored.prices.ebay_new_bin.median if scored.prices.ebay_new_bin.status == "ok" else None,
                    market_used_price=scored.prices.ebay_used_bin.median if scored.prices.ebay_used_bin.status == "ok" else None,
                    classification=scored.classification,
                    deal_score=scored.deal_score,
                    confidence_score=scored.confidence_score,
                    confidence_band=scored.confidence_band,
                    decision=scored.decision,
                    reasoning_summary=scored.reasoning_summary,
                    release_year=scored.release_year,
                    listing_observed_at=listing.extracted_at.replace(tzinfo=None) if listing.extracted_at.tzinfo else listing.extracted_at,
                )
                db.add(db_row)

                # Track pricing source
                if scored.prices.ebay_new_bin.median or scored.prices.ebay_used_bin.median:
                    priced_count += 1
                    if scored.prices.ebay_new_bin.source == "cpk_consolidation" or scored.prices.ebay_used_bin.source == "cpk_consolidation":
                        cpk_priced += 1

                if scored.classification == "SUPER_GEM":
                    super_gem += 1
                elif scored.classification == "GEM":
                    gem += 1

                if i % 100 == 0:
                    await db.commit()
                    elapsed = (datetime.now(timezone.utc) - start_time).total_seconds()
                    rate = i / elapsed if elapsed > 0 else 0
                    pct = 100 * priced_count // i if i > 0 else 0
                    cpk_pct = 100 * cpk_priced // priced_count if priced_count > 0 else 0
                    print(f"[{i:5d}/{total}] Priced: {priced_count:5d} ({pct}%) | CPK-sourced: {cpk_priced:5d} ({cpk_pct}%) | GEM: {gem:4d} | SUPER_GEM: {super_gem:4d} | Rate: {rate:.1f}/s")

            except Exception as exc:
                log.error("rescore_failed", listing_id=row[0], error=str(exc))
                continue

        await db.commit()

        elapsed = (datetime.now(timezone.utc) - start_time).total_seconds()
        print()
        print("=" * 80)
        print(f"Rescoring Complete!")
        print("=" * 80)
        print(f"  Total: {total}")
        print(f"  Priced: {priced_count} ({100*priced_count//total if total > 0 else 0}%)")
        print(f"  Priced via CPK: {cpk_priced} ({100*cpk_priced//priced_count if priced_count > 0 else 0}%)")
        print(f"  GEM: {gem}")
        print(f"  SUPER_GEM: {super_gem}")
        print(f"  Elapsed: {elapsed:.1f}s ({elapsed/60:.1f}m)")
        print()


async def main():
    try:
        await consolidate_and_rescore()
    except KeyboardInterrupt:
        print("\nInterrupted")
        sys.exit(1)
    except Exception as exc:
        print(f"Error: {exc}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
