"""One-off backfill: re-run BIN price matching against every currently-scored
listing that has NO price benchmark at all (market_new_price AND
market_used_price both NULL), using the current (post-fix) batch price index
— lower MIN_SAMPLE_FOR_MEDIAN, marketplace-aware pooling that excludes Temu.

Unlike scripts/recompute_gem_radar_scores.py (which only re-runs the scoring
arithmetic against each listing's ORIGINAL, cached PriceBundle), this
actually re-fetches new BIN benchmarks — the whole point is that many
listings that had NO match under the old (stricter, unfiltered) index should
now find one under the improved index, without needing to wait for their
next natural re-scan.

Deliberately BIN-only, no live network calls:
  - Sold comps: left "unavailable" — the live scraper is blocked (403) and
    hitting it per-listing here would be slow for no benefit; a listing's
    next real scan will pick up sold comps normally if that ever changes.
  - Amazon: left "unavailable" — no credentials configured (see
    adapters/amazon_price.py).
This mirrors the live pipeline's own fallback order (sold -> BIN -> Amazon)
in the specific case where sold/Amazon are already known-unavailable, so a
listing that finds a BIN match here scores identically to how a fresh scan
would score it today.

Only touches rows currently missing ALL price data — a listing that already
has SOME price benchmark (even a partial one) is left alone; re-litigating
already-priced listings is out of scope for this backfill.

Usage:
    python scripts/backfill_bin_prices.py                                    # dry run
    python scripts/backfill_bin_prices.py --apply                            # write changes
    python scripts/backfill_bin_prices.py --apply --backup-file backup.json  # snapshot old values first
"""
from __future__ import annotations

import argparse
import asyncio
import json
import sys
from collections import Counter
from datetime import datetime, timezone

sys.path.insert(0, ".")

from sqlalchemy import select

from app.database import AsyncSessionLocal
from app.gem_radar import identity as identity_mod
from app.gem_radar import risk as risk_mod
from app.gem_radar import scoring
from app.gem_radar.benchmarks import _unavailable_stat, fetch_bin_benchmarks, normalize_match_key
from app.gem_radar.pipeline import _epid_key, _merge_bucket_dicts, build_batch_price_index
from app.gem_radar.schemas import ExtractedListing, Identity, PriceBundle
from app.models.gem_radar_scored_listing import GemRadarScoredListing

_BATCH_SIZE = 500


def _build_listing(row: GemRadarScoredListing) -> ExtractedListing:
    condition = row.condition or "unknown"
    return ExtractedListing(
        listingId=row.listing_id,
        url=f"https://www.ebay.co.uk/itm/{row.listing_id}",
        title=row.title,
        seller=row.seller_name,
        sellerFeedbackPercent=None,
        sellerFeedbackCount=None,
        conditionRaw=condition if condition != "unknown" else None,
        conditionNormalised=condition,
        itemPrice=row.actual_listing_price,
        postagePrice=row.postage_price,
        currentDeliveredPrice=row.delivered_price,
        listingType="buy_it_now",
        bestOfferEnabled=False,
        bidCount=None,
        auctionEndAt=None,
        imageUrl=row.image_url,
        sponsored=False,
        epid=row.epid,
        extractedAt=row.listing_observed_at.replace(tzinfo=timezone.utc)
        if row.listing_observed_at and row.listing_observed_at.tzinfo is None
        else (row.listing_observed_at or datetime.now(timezone.utc)),
    )


def _build_price_bundle(row: GemRadarScoredListing, batch_price_index: dict) -> tuple[PriceBundle, str] | None:
    """Returns (bundle, match_level) if a real BIN match was found, else None
    (nothing worth writing — leave the row exactly as it was)."""
    match_key = row.canonical_model_id or identity_mod.resolve_identity(row.title).model
    if not match_key:
        return None
    match_level = "exact_model_variant" if row.canonical_model_id else "category_comparable"

    batch_entries = batch_price_index.get(normalize_match_key(match_key))
    # epid (eBay catalog product ID) is a stronger identity signal than any
    # title-derived key — merge it in additively, same as the live pipeline
    # (see pipeline._get_or_compute_research), rather than replacing
    # batch_entries outright.
    if row.epid:
        epid_entries = batch_price_index.get(_epid_key(row.epid))
        if epid_entries:
            batch_entries = _merge_bucket_dicts(batch_entries, epid_entries)
            match_level = "exact_model_variant"
    new_bin, used_bin = fetch_bin_benchmarks(
        row.condition or "unknown", match_level, batch_entries, row.listing_id
    )
    relevant = new_bin if (row.condition or "") in ("new", "new_other") else used_bin
    if relevant.status != "ok":
        return None

    return (
        PriceBundle(
            actualListing=row.delivered_price,
            ebayNewBin=new_bin,
            ebayUsedBin=used_bin,
            ebayNewSold=_unavailable_stat("sold-comps adapter", "Not re-fetched in backfill — see script docstring"),
            ebayUsedSold=_unavailable_stat("sold-comps adapter", "Not re-fetched in backfill — see script docstring"),
            amazonUkNew=_unavailable_stat("Amazon UK", "No Amazon pricing API credentials configured"),
        ),
        match_level,
    )


def _recompute(row: GemRadarScoredListing, prices: PriceBundle, match_level: str) -> dict:
    listing = _build_listing(row)
    identity = Identity(
        brand=None,
        model=row.canonical_model_id or identity_mod.resolve_identity(row.title).model,
        mpn=None,
        category=row.category,
        exactSkuConfidence=1.0 if match_level == "exact_model_variant" else 0.5,
        modelCanonical=row.canonical_model_id,
    )
    risk_flags = risk_mod.detect_risk_flags(listing.title, listing.condition_raw)
    penalty = risk_mod.risk_penalty(risk_flags)

    deal_score, benchmark_label = scoring.compute_deal_score(listing, prices, penalty)
    market_stat, _ = scoring.pick_condition_benchmark(listing.condition_normalised, prices)
    classification = scoring.classify(
        deal_score, benchmark_label, identity.category, listing.current_delivered_price, market_stat
    )
    confidence_score, confidence_band = scoring.compute_confidence(
        identity, prices, listing.condition_normalised, listing, benchmark_label
    )
    decision = scoring.compute_decision(classification, confidence_band, risk_flags)

    new_bin_price = prices.ebay_new_bin.average if prices.ebay_new_bin.status == "ok" else None
    used_bin_price = prices.ebay_used_bin.average if prices.ebay_used_bin.status == "ok" else None

    return {
        "market_new_price": new_bin_price,
        "market_used_price": used_bin_price,
        "deal_score": deal_score,
        "classification": classification,
        "confidence_score": confidence_score,
        "confidence_band": confidence_band,
        "decision": decision,
    }


async def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--apply", action="store_true", help="Actually write changes (default is dry-run).")
    parser.add_argument(
        "--backup-file",
        default=None,
        help="If given (with --apply), write the pre-change values of every touched row to this JSON file first.",
    )
    args = parser.parse_args()

    async with AsyncSessionLocal() as db:
        print("Building current batch price index (this may take a moment)...")
        batch_price_index = await build_batch_price_index(db, [])
        print(f"  {len(batch_price_index)} resolved model keys in the index.\n")

        total = 0
        no_match_key = 0
        no_price_found = 0
        backfilled = 0
        classification_transitions: Counter[tuple[str, str]] = Counter()
        new_classification_counts: Counter[str] = Counter()
        old_classification_counts: Counter[str] = Counter()
        backup_rows: list[dict] = []

        offset = 0
        while True:
            result = await db.execute(
                select(GemRadarScoredListing)
                .where(
                    GemRadarScoredListing.market_new_price.is_(None),
                    GemRadarScoredListing.market_used_price.is_(None),
                )
                .order_by(GemRadarScoredListing.id)
                .offset(offset)
                .limit(_BATCH_SIZE)
            )
            batch = result.scalars().all()
            if not batch:
                break

            for row in batch:
                total += 1
                old_classification_counts[row.classification] += 1

                built = _build_price_bundle(row, batch_price_index)
                if built is None:
                    no_price_found += 1
                    new_classification_counts[row.classification] += 1
                    continue
                prices, match_level = built

                new = _recompute(row, prices, match_level)
                backfilled += 1
                new_classification_counts[new["classification"]] += 1
                if new["classification"] != row.classification:
                    classification_transitions[(row.classification, new["classification"])] += 1

                if args.backup_file:
                    backup_rows.append(
                        {
                            "id": row.id,
                            "listing_id": row.listing_id,
                            "old": {
                                "market_new_price": row.market_new_price,
                                "market_used_price": row.market_used_price,
                                "deal_score": row.deal_score,
                                "classification": row.classification,
                                "confidence_score": row.confidence_score,
                                "confidence_band": row.confidence_band,
                                "decision": row.decision,
                            },
                        }
                    )

                if args.apply:
                    row.market_new_price = new["market_new_price"]
                    row.market_used_price = new["market_used_price"]
                    row.deal_score = new["deal_score"]
                    row.classification = new["classification"]
                    row.confidence_score = new["confidence_score"]
                    row.confidence_band = new["confidence_band"]
                    row.decision = new["decision"]

            if args.apply:
                await db.commit()

            offset += _BATCH_SIZE
            print(f"  processed {offset}...", end="\r")

        if args.backup_file and backup_rows:
            with open(args.backup_file, "w") as f:
                json.dump(backup_rows, f, indent=2)
            print(f"\nWrote pre-change snapshot of {len(backup_rows)} rows to {args.backup_file}")

        print()
        print(f"Total rows with no price data examined: {total}")
        print(f"Still no match found (index has nothing for this model): {no_price_found}")
        print(f"Backfilled with a real BIN price: {backfilled}")
        print()
        print("Classification distribution BEFORE:")
        for cls, count in sorted(old_classification_counts.items()):
            print(f"  {cls:14s} {count}")
        print()
        print("Classification distribution AFTER" + (" (dry run — not written)" if not args.apply else "") + ":")
        for cls, count in sorted(new_classification_counts.items()):
            print(f"  {cls:14s} {count}")
        print()
        if classification_transitions:
            print("Classification transitions:")
            for (old, new), count in sorted(classification_transitions.items(), key=lambda kv: -kv[1]):
                print(f"  {old:14s} -> {new:14s}  {count}")
        if not args.apply:
            print("\nDry run only — re-run with --apply to write these changes to the database.")


if __name__ == "__main__":
    asyncio.run(main())
