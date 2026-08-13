"""
Rescore all listings using new CPK-based pricing.

Clears existing scores and re-runs the scoring pipeline with CPK
consolidation enabled, measuring the improvement in pricing coverage
and deal quality.

Usage:
  python scripts/rescore_with_cpk.py [--limit 100]
"""
from __future__ import annotations

import asyncio
import sys
import argparse
from pathlib import Path
from datetime import datetime, timezone

sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import text
from app.database import AsyncSessionLocal
from app.gem_radar.pipeline import build_batch_price_index, score_listing
from app.gem_radar.adapters.sold_comps import UnavailableSoldCompsAdapter
from app.gem_radar.adapters.amazon_price import UnavailableAmazonPriceAdapter
from app.models.gem_radar_scored_listing import GemRadarScoredListing
from app.models.gem_radar_observation import GemRadarListingObservation

import structlog

log = structlog.get_logger(__name__)


async def rescore_with_cpk(limit: int | None = None):
    """Rescore all listings using CPK-based pricing."""
    async with AsyncSessionLocal() as db:
        # Get all listings with CPK that need rescoring
        query = """
        SELECT
            lo.listing_id, lo.title, lo.seller_name, lo.image_url,
            lo.condition_normalised, lo.item_price, lo.postage_price,
            lo.delivered_price, lo.listing_type, lo.best_offer_enabled,
            lo.bid_count, lo.source, gs.cpk
        FROM gem_radar_listing_observations lo
        LEFT JOIN gem_radar_scored_listings gs ON lo.listing_id = gs.listing_id
        WHERE lo.listing_id IN (
            SELECT DISTINCT listing_id FROM gem_radar_scored_listings WHERE cpk IS NOT NULL
        )
        ORDER BY lo.observed_at DESC
        """
        if limit:
            query += f" LIMIT {limit}"

        result = await db.execute(text(query))
        listings = result.fetchall()

        if not listings:
            print("No CPK listings to rescore.")
            return

        total = len(listings)
        print(f"Rescoring {total} listings with CPK pricing...")
        print()

        # Clear existing scores for these listings
        listing_ids = [row[0] for row in listings]
        from sqlalchemy import delete, column
        await db.execute(
            text(f"DELETE FROM gem_radar_scored_listings WHERE listing_id IN ({','.join([repr(lid) for lid in listing_ids])})")
        )
        await db.commit()

        # Rescore with CPK enabled
        sold_adapter = UnavailableSoldCompsAdapter()
        amazon_adapter = UnavailableAmazonPriceAdapter()

        priced_count = 0
        super_gem = 0
        gem = 0
        start_time = datetime.now(timezone.utc)

        for i, row in enumerate(listings, 1):
            try:
                # Convert tuple to dict for ExtractedListing
                from app.gem_radar.schemas import ExtractedListing
                from datetime import datetime as dt

                listing_dict = {
                    "listingId": row[0],
                    "url": f"https://ebay.co.uk/itm/{row[0]}",  # Placeholder
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
                    "extractedAt": dt.now(timezone.utc),
                }
                listing = ExtractedListing(**listing_dict)

                # Score with CPK
                scored = await score_listing(
                    db, listing, rank=i, sold_adapter=sold_adapter,
                    amazon_adapter=amazon_adapter, deep_research=False
                )

                # Save to database
                db_row = GemRadarScoredListing(
                    listing_id=scored.listing.listing_id,
                    search_run_id="rescore-cpk",
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

                if scored.prices.ebay_new_bin.median or scored.prices.ebay_used_bin.median:
                    priced_count += 1
                if scored.classification == "SUPER_GEM":
                    super_gem += 1
                elif scored.classification == "GEM":
                    gem += 1

                if i % 50 == 0:
                    await db.commit()
                    elapsed = (datetime.now(timezone.utc) - start_time).total_seconds()
                    rate = i / elapsed if elapsed > 0 else 0
                    print(f"[{i:5d}/{total}] Rescored | Priced: {priced_count:4d} ({100*priced_count//i}%) | GEM: {gem:3d} | SUPER_GEM: {super_gem:3d} | Rate: {rate:.1f}/s")

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
        print(f"  GEM: {gem}")
        print(f"  SUPER_GEM: {super_gem}")
        print(f"  Elapsed: {elapsed:.1f}s")
        print()


async def main():
    parser = argparse.ArgumentParser(description="Rescore listings using CPK-based pricing")
    parser.add_argument("--limit", type=int, default=None, help="Max listings to rescore")
    args = parser.parse_args()

    try:
        await rescore_with_cpk(limit=args.limit)
    except KeyboardInterrupt:
        print("\nInterrupted by user")
        sys.exit(1)
    except Exception as exc:
        print(f"Error: {exc}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
