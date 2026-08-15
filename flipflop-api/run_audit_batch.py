#!/usr/bin/env python3
"""Run multiple audit samples automatically"""
import asyncio
import json
from datetime import datetime, timedelta
from pathlib import Path
from sqlalchemy import select, func
from app.database import AsyncSessionLocal
from app.models.gem_radar_scored_listing import GemRadarScoredListing

def format_listing_for_review(listing, index):
    """Format a listing for human review"""
    market_prices = None
    if listing.market_new_price or listing.market_used_price:
        market_prices = {
            "new": float(listing.market_new_price) if listing.market_new_price else None,
            "used": float(listing.market_used_price) if listing.market_used_price else None,
        }

    return {
        "index": index + 1,
        "listing_id": listing.listing_id,
        "title": listing.title[:80],
        "category": listing.category,
        "delivered_price": float(listing.delivered_price),
        "item_price": float(listing.actual_listing_price),
        "postage_price": float(listing.postage_price),
        "market_prices": market_prices,
        "classification": listing.classification,
        "deal_score": float(listing.deal_score) if listing.deal_score else None,
        "url": listing.url,
        "condition": listing.condition,
        "seller": listing.seller_name,
    }

async def get_random_sample(sample_size=50):
    """Get random sample of listings across all categories"""
    async with AsyncSessionLocal() as db:
        week_ago = datetime.utcnow() - timedelta(days=7)
        stmt = select(GemRadarScoredListing).where(
            GemRadarScoredListing.scored_at >= week_ago
        ).order_by(func.random()).limit(sample_size)
        result = await db.execute(stmt)
        return result.scalars().all()

async def run_sample(sample_num):
    """Run one audit sample"""
    print(f"\n{'='*80}")
    print(f"SAMPLE {sample_num} - Loading 50 random listings...")
    print(f"{'='*80}\n")

    listings = await get_random_sample(50)
    if not listings:
        print("No listings found")
        return None

    sample_data = {
        "sample_number": sample_num,
        "timestamp": datetime.utcnow().isoformat(),
        "total_listings": len(listings),
        "listings": [format_listing_for_review(l, i) for i, l in enumerate(listings)]
    }

    # Print summary
    categories = {}
    for listing in listings:
        cat = listing.category or "unknown"
        if cat not in categories:
            categories[cat] = {"count": 0, "gems": 0, "prices": []}
        categories[cat]["count"] += 1
        if listing.classification in ("GEM", "SUPER_GEM"):
            categories[cat]["gems"] += 1
        categories[cat]["prices"].append(float(listing.delivered_price))

    print("CATEGORY BREAKDOWN:")
    print("-" * 70)
    for cat in sorted(categories.keys()):
        data = categories[cat]
        avg = sum(data["prices"]) / len(data["prices"]) if data["prices"] else 0
        print(f"  {cat:15} | Count: {data['count']:3} | Gems: {data['gems']:2} | Avg: £{avg:8.2f}")

    print("\n" + "="*80)
    print(f"Sample {sample_num}: {len(listings)} listings loaded - Ready for AI review")
    print("="*80)

    # Save
    audit_dir = Path(__file__).parent / "audit_results"
    audit_dir.mkdir(exist_ok=True)
    audit_file = audit_dir / f"sample_{sample_num}.json"
    with open(audit_file, "w") as f:
        json.dump(sample_data, f, indent=2)

    return sample_data

async def main():
    # Run samples 4-5 to test fixes
    for i in range(4, 6):
        data = await run_sample(i)
        if data:
            print(f"\n[OK] Sample {i} data saved")
        else:
            print(f"\n[FAIL] Sample {i} failed")

        if i < 3:
            print("\nReady for AI audit...")

    print("\n" + "="*70)
    print("All samples generated. Ready for AI analysis.")
    print("="*70)

if __name__ == "__main__":
    asyncio.run(main())
