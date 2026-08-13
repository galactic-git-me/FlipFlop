"""One-off RESCUE: every listing_id currently "active" (per
observations.get_active_listing_ids) but with NO row in
gem_radar_scored_listings at all is stuck in permanent limbo — kept alive
by repeated dedup/touch cycles, but never scored, because the observation
that would have been used to dedupe a retried submission was written by
that SAME interrupted submission (see observations.get_recent_observation's
exclude_search_run_id fix, which stops this from happening going forward).

This reconstructs each orphan from its most recent observation row and runs
it through the real scoring pipeline once, giving it the
gem_radar_scored_listings row it should already have.

Skips listing_ids matching the "XXX-XXX-#####" synthetic pattern used by a
separate catalogue/configurator feature that also writes to
gem_radar_listing_observations — those were never real marketplace listings
and were never meant to appear on the sourcing dashboard.

Real scraped URLs aren't stored on the observation row (only on
gem_radar_scored_listings, and only since this session's url-column fix), so
rescued rows get a source-aware fallback URL (see marketplace.
fallback_listing_url) rather than the real original link.

Usage:
    python scripts/rescue_orphaned_active_listings.py                                    # dry run
    python scripts/rescue_orphaned_active_listings.py --apply
    python scripts/rescue_orphaned_active_listings.py --apply --backup-file backup.json
"""
from __future__ import annotations

import argparse
import asyncio
import json
import re
import sys
from collections import Counter
from datetime import timezone

sys.path.insert(0, ".")

from sqlalchemy import select

from app.database import AsyncSessionLocal
from app.gem_radar.adapters.amazon_price import UnavailableAmazonPriceAdapter
from app.gem_radar.adapters.sold_comps import UnavailableSoldCompsAdapter
from app.gem_radar.marketplace import fallback_listing_url, infer_marketplace
from app.gem_radar.observations import get_active_listing_ids
from app.gem_radar.pipeline import build_batch_price_index, score_listing
from app.gem_radar.schemas import ExtractedListing
from app.models.gem_radar_observation import GemRadarListingObservation
from app.models.gem_radar_scored_listing import GemRadarScoredListing

# Catalogue/configurator SKU shapes: digit-suffix ("POW-ASU-07631") and
# letter-suffix ("CM-010-KK") variants both observed in the orphan set —
# neither is a real marketplace listing.
_SYNTHETIC_ID_PATTERN = re.compile(r"^[A-Z]{2,4}-[A-Z0-9]{2,4}-[A-Z0-9]{2,6}$")


def _build_listing(obs: GemRadarListingObservation) -> ExtractedListing:
    condition = obs.condition_normalised or "unknown"
    url = fallback_listing_url(obs.listing_id, obs.source)
    return ExtractedListing(
        listingId=obs.listing_id,
        url=url,
        title=obs.title,
        seller=obs.seller_name,
        sellerFeedbackPercent=None,
        sellerFeedbackCount=None,
        conditionRaw=condition if condition != "unknown" else None,
        conditionNormalised=condition,
        itemPrice=obs.item_price,
        postagePrice=obs.postage_price,
        currentDeliveredPrice=obs.delivered_price,
        listingType=obs.listing_type or "buy_it_now",
        bestOfferEnabled=obs.best_offer_enabled,
        bidCount=obs.bid_count,
        auctionEndAt=None,
        imageUrl=obs.image_url,
        sponsored=False,
        extractedAt=obs.observed_at.replace(tzinfo=timezone.utc)
        if obs.observed_at and obs.observed_at.tzinfo is None
        else obs.observed_at,
    )


async def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--apply", action="store_true", help="Actually write changes (default is dry-run).")
    parser.add_argument(
        "--backup-file", default=None,
        help="If given (with --apply), write the listing_ids rescued to this JSON file first.",
    )
    args = parser.parse_args()

    async with AsyncSessionLocal() as db:
        print("Finding active listings with no scored row...")
        active_ids = await get_active_listing_ids(db)
        scored_ids_result = await db.execute(
            select(GemRadarScoredListing.listing_id).distinct().where(
                GemRadarScoredListing.listing_id.in_(active_ids)
            )
        )
        scored_ids = {r[0] for r in scored_ids_result.all()}
        orphan_ids = active_ids - scored_ids
        synthetic_skipped = [lid for lid in orphan_ids if _SYNTHETIC_ID_PATTERN.match(lid)]
        rescuable_ids = [lid for lid in orphan_ids if not _SYNTHETIC_ID_PATTERN.match(lid)]
        print(f"  {len(orphan_ids)} orphaned active listings total")
        print(f"  {len(synthetic_skipped)} skipped (synthetic catalogue-pattern IDs, not real listings)")
        print(f"  {len(rescuable_ids)} to rescue\n")

        if not rescuable_ids:
            print("Nothing to rescue.")
            return

        print("Fetching each orphan's most recent observation...")
        obs_by_listing: dict[str, GemRadarListingObservation] = {}
        for lid in rescuable_ids:
            result = await db.execute(
                select(GemRadarListingObservation)
                .where(GemRadarListingObservation.listing_id == lid)
                .order_by(GemRadarListingObservation.observed_at.desc())
                .limit(1)
            )
            row = result.scalar_one_or_none()
            if row is not None:
                obs_by_listing[lid] = row

        listings = [_build_listing(obs) for obs in obs_by_listing.values()]
        print(f"  reconstructed {len(listings)} listings\n")

        print("Building batch price index (existing history + these listings pooled together)...")
        batch_price_index = await build_batch_price_index(db, listings)

        sold_adapter = UnavailableSoldCompsAdapter()
        amazon_adapter = UnavailableAmazonPriceAdapter()

        classification_counts: Counter[str] = Counter()
        rescued: list[dict] = []
        failed = 0

        for i, listing in enumerate(listings, start=1):
            try:
                result = await score_listing(
                    db, listing, rank=i, sold_adapter=sold_adapter, amazon_adapter=amazon_adapter,
                    deep_research=False, batch_price_index=batch_price_index,
                )
            except Exception as exc:
                failed += 1
                print(f"  failed to score {listing.listing_id}: {exc}")
                continue

            classification_counts[result.classification] += 1
            obs = obs_by_listing[listing.listing_id]
            computed_source = infer_marketplace(listing.url) or obs.source or "ebay"
            rescued.append({
                "listing_id": listing.listing_id,
                "source": computed_source,
                "classification": result.classification,
                "row": GemRadarScoredListing(
                    listing_id=listing.listing_id,
                    search_run_id=obs.search_run_id,
                    source=computed_source,
                    url=listing.url,
                    title=listing.title,
                    seller_name=listing.seller,
                    image_url=listing.image_url,
                    condition=listing.condition_normalised,
                    category=result.identity.category,
                    canonical_model_id=result.identity.model_canonical,
                    actual_listing_price=listing.item_price,
                    postage_price=listing.postage_price,
                    delivered_price=listing.current_delivered_price,
                    market_new_price=result.prices.ebay_new_bin.average if result.prices.ebay_new_bin.status == "ok" else None,
                    market_used_price=result.prices.ebay_used_bin.average if result.prices.ebay_used_bin.status == "ok" else None,
                    classification=result.classification,
                    deal_score=result.deal_score,
                    confidence_score=result.confidence_score,
                    confidence_band=result.confidence_band,
                    decision=result.decision,
                    reasoning_summary=result.reasoning_summary,
                    release_year=result.release_year,
                    listing_observed_at=listing.extracted_at.replace(tzinfo=None) if listing.extracted_at.tzinfo else listing.extracted_at,
                ),
            })
            if i % 200 == 0:
                print(f"  scored {i}/{len(listings)}...")

        print()
        print(f"Scored successfully: {len(rescued)} / {len(listings)} (failed: {failed})")
        print("Classification distribution:")
        for cls, count in sorted(classification_counts.items(), key=lambda kv: -kv[1]):
            print(f"  {cls:14s} {count}")
        source_counts = Counter(r["source"] for r in rescued)
        print("\nBy source:")
        for source, count in source_counts.most_common():
            print(f"  {str(source):14s} {count}")

        if args.apply:
            if args.backup_file:
                with open(args.backup_file, "w", encoding="utf-8") as f:
                    json.dump([{"listing_id": r["listing_id"], "source": r["source"]} for r in rescued], f, indent=2)
                print(f"\nWrote rescued listing_id list to {args.backup_file}")
            for r in rescued:
                db.add(r["row"])
            await db.commit()
            print(f"\nCommitted {len(rescued)} new gem_radar_scored_listings rows.")
        else:
            print("\nDry run only — re-run with --apply to write these rows to the database.")


if __name__ == "__main__":
    asyncio.run(main())
