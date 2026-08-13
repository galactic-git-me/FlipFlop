"""One-off backfill: recompute deal_score/classification/confidence/decision
for every row in gem_radar_scored_listings (active AND inactive — no
get_active_listing_ids filter) after scoring.py dropped the seller_trust and
time_sensitivity sub-scores and redistributed their weight across the rest
(see scoring.py's module docstring for why).

Does NOT re-fetch market prices or re-run Claude — it's a pure re-run of the
arithmetic in scoring.py against the identity/PriceBundle already cached for
each listing_id in gem_radar_listing_observations.scored_result_json (written
by every real scan via observations.store_cached_research), plus the fields
already persisted on the gem_radar_scored_listings row itself. Every listing_id
in gem_radar_scored_listings maps 1:1 to exactly one such row today (verified
before writing this script), so this is an exact recompute of the same
identity/price evidence used at original scoring time — not a fresh scan
against today's market.

Known approximation: neither table persists the listing's original raw
condition text (conditionRaw) or its risk flags, only condition_normalised
and title. Risk flags are re-derived from title text alone via
risk.detect_risk_flags(title, condition_raw=None) — condition_raw text
often duplicates the same wording already in the title (e.g. "for parts"),
so this recovers the same flags in practice, but a flag that ONLY appeared in
condition_raw text distinct from the title would be missed. Listing
completeness's condition_raw field is approximated as "present" whenever
condition_normalised is a real value (not null/"unknown"), since the
extractor only ever produces "unknown" when no condition text was found on
the card at all.

Only touches the 5 columns that are actually a function of deal_score's
inputs: deal_score, classification, confidence_score, confidence_band,
decision. Everything else on the row (prices, category, timestamps,
reasoning_summary, canonical_model_id, ...) is left untouched.

Usage:
    python scripts/recompute_gem_radar_scores.py            # dry run, prints a summary, writes nothing
    python scripts/recompute_gem_radar_scores.py --apply     # actually updates the database
    python scripts/recompute_gem_radar_scores.py --apply --backup-file backup.json  # also snapshot old values first
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
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import AsyncSessionLocal
from app.gem_radar import risk as risk_mod
from app.gem_radar import scoring
from app.gem_radar.schemas import ExtractedListing, Identity, PriceBundle
from app.models.gem_radar_observation import GemRadarListingObservation
from app.models.gem_radar_scored_listing import GemRadarScoredListing

_BATCH_SIZE = 500


def _build_listing(row: GemRadarScoredListing) -> ExtractedListing:
    condition = row.condition or "unknown"
    return ExtractedListing(
        listingId=row.listing_id,
        url=f"https://www.ebay.co.uk/itm/{row.listing_id}",
        title=row.title,
        seller=row.seller_name,
        sellerFeedbackPercent=None,  # never persisted (see module docstring)
        sellerFeedbackCount=None,
        # condition_raw text isn't persisted anywhere — approximate presence
        # (for listing_completeness) as "there was a real condition reading"
        # rather than fabricate the original string.
        conditionRaw=condition if condition != "unknown" else None,
        conditionNormalised=condition,
        itemPrice=row.actual_listing_price,
        postagePrice=row.postage_price,
        currentDeliveredPrice=row.delivered_price,
        listingType="buy_it_now",  # no longer affects deal_score (time_sensitivity removed)
        bestOfferEnabled=False,
        bidCount=None,
        auctionEndAt=None,
        imageUrl=row.image_url,
        sponsored=False,
        extractedAt=row.listing_observed_at.replace(tzinfo=timezone.utc)
        if row.listing_observed_at and row.listing_observed_at.tzinfo is None
        else (row.listing_observed_at or datetime.now(timezone.utc)),
    )


async def _load_cached_research(db: AsyncSession, listing_id: str) -> tuple[Identity, PriceBundle] | None:
    result = await db.execute(
        select(GemRadarListingObservation.scored_result_json)
        .where(
            GemRadarListingObservation.listing_id == listing_id,
            GemRadarListingObservation.scored_result_json.is_not(None),
        )
        .order_by(GemRadarListingObservation.scored_at.desc())
        .limit(1)
    )
    raw = result.scalar_one_or_none()
    if raw is None:
        return None
    data = json.loads(raw)
    return Identity.model_validate(data["identity"]), PriceBundle.model_validate(data["prices"])


def _recompute(row: GemRadarScoredListing, identity: Identity, prices: PriceBundle) -> dict:
    listing = _build_listing(row)
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

    return {
        "deal_score": deal_score,
        "classification": classification,
        "confidence_score": confidence_score,
        "confidence_band": confidence_band,
        "decision": decision,
    }


async def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true", help="Actually write changes (default is dry-run).")
    parser.add_argument(
        "--backup-file",
        default=None,
        help="If given (with --apply), write the pre-change values of every touched row to this JSON file first.",
    )
    args = parser.parse_args()

    async with AsyncSessionLocal() as db:
        total = 0
        skipped_no_research = 0
        changed = 0
        classification_transitions: Counter[tuple[str, str]] = Counter()
        new_classification_counts: Counter[str] = Counter()
        old_classification_counts: Counter[str] = Counter()
        backup_rows: list[dict] = []

        offset = 0
        while True:
            result = await db.execute(
                select(GemRadarScoredListing).order_by(GemRadarScoredListing.id).offset(offset).limit(_BATCH_SIZE)
            )
            batch = result.scalars().all()
            if not batch:
                break

            for row in batch:
                total += 1
                old_classification_counts[row.classification] += 1

                research = await _load_cached_research(db, row.listing_id)
                if research is None:
                    skipped_no_research += 1
                    continue
                identity, prices = research

                new = _recompute(row, identity, prices)
                new_classification_counts[new["classification"]] += 1

                if new["classification"] != row.classification or abs(new["deal_score"] - row.deal_score) > 1e-9:
                    changed += 1
                    classification_transitions[(row.classification, new["classification"])] += 1

                    if args.backup_file:
                        backup_rows.append(
                            {
                                "id": row.id,
                                "listing_id": row.listing_id,
                                "old": {
                                    "deal_score": row.deal_score,
                                    "classification": row.classification,
                                    "confidence_score": row.confidence_score,
                                    "confidence_band": row.confidence_band,
                                    "decision": row.decision,
                                },
                            }
                        )

                    if args.apply:
                        row.deal_score = new["deal_score"]
                        row.classification = new["classification"]
                        row.confidence_score = new["confidence_score"]
                        row.confidence_band = new["confidence_band"]
                        row.decision = new["decision"]

            if args.apply:
                await db.commit()

            offset += _BATCH_SIZE
            print(f"  processed {min(offset, total + skipped_no_research + (0 if batch else 0))}...", end="\r")

        if args.backup_file and backup_rows:
            with open(args.backup_file, "w") as f:
                json.dump(backup_rows, f, indent=2)
            print(f"\nWrote pre-change snapshot of {len(backup_rows)} rows to {args.backup_file}")

        print()
        print(f"Total rows examined:        {total}")
        print(f"Skipped (no cached research): {skipped_no_research}")
        print(f"Rows with a changed score/classification: {changed}")
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
                if old != new:
                    print(f"  {old:14s} -> {new:14s}  {count}")
        if not args.apply:
            print("\nDry run only — re-run with --apply to write these changes to the database.")


if __name__ == "__main__":
    asyncio.run(main())
