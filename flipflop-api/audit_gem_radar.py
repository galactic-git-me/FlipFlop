#!/usr/bin/env python3
"""Rigorous testing of gem radar: prices, relevance, classification, deal scores"""
import asyncio
import json
from datetime import datetime, timedelta
from sqlalchemy import select, func
from app.database import AsyncSessionLocal
from app.models.gem_radar_scored_listing import GemRadarScoredListing

async def get_random_sample(sample_size=50):
    """Get random sample of listings across all categories"""
    async with AsyncSessionLocal() as db:
        # Get listings from past week (recent data)
        week_ago = datetime.utcnow() - timedelta(days=7)

        stmt = select(GemRadarScoredListing).where(
            GemRadarScoredListing.scored_at >= week_ago
        ).order_by(func.random()).limit(sample_size)

        result = await db.execute(stmt)
        listings = result.scalars().all()

        return listings

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
        "title": listing.title[:80],  # Truncate for readability
        "category": listing.category,
        "delivered_price": float(listing.delivered_price),
        "item_price": float(listing.actual_listing_price),
        "postage_price": float(listing.postage_price),
        "market_prices": market_prices,  # eBay market new/used prices at scrape time
        "classification": listing.classification,
        "deal_score": float(listing.deal_score) if listing.deal_score else None,
        "url": listing.url,
        "condition": listing.condition,
        "seller": listing.seller_name,
    }

async def run_audit_sample(sample_num):
    """Run one audit sample and return raw data for user review"""
    print(f"\n{'='*80}")
    print(f"SAMPLE {sample_num} - Loading 50 random listings...")
    print(f"{'='*80}\n")

    listings = await get_random_sample(50)

    if not listings:
        print("No listings found in database")
        return None

    sample_data = {
        "sample_number": sample_num,
        "timestamp": datetime.utcnow().isoformat(),
        "total_listings": len(listings),
        "listings": [format_listing_for_review(l, i) for i, l in enumerate(listings)]
    }

    # Print summaries
    categories = {}
    for listing in listings:
        cat = listing.category or "unknown"
        if cat not in categories:
            categories[cat] = {"count": 0, "gems": 0, "prices": []}
        categories[cat]["count"] += 1
        if listing.classification in ("GEM", "SUPER_GEM"):
            categories[cat]["gems"] += 1
        categories[cat]["prices"].append(float(listing.delivered_price))

    print("\nLISTINGS BY CATEGORY:")
    print("-" * 60)
    for cat in sorted(categories.keys()):
        data = categories[cat]
        avg_price = sum(data["prices"]) / len(data["prices"]) if data["prices"] else 0
        print(f"  {cat:15} | Count: {data['count']:3} | Gems: {data['gems']:2} | Avg Price: £{avg_price:8.2f}")

    print("\n" + "="*80)
    print("SAMPLE DATA READY FOR REVIEW")
    print("="*80)
    print(f"\nTotal listings loaded: {len(listings)}")
    print(f"Date range: Past 7 days")
    print(f"Sample timestamp: {datetime.utcnow().isoformat()}")

    # Save to file for reference
    from pathlib import Path
    audit_dir = Path(__file__).parent / "audit_results"
    audit_dir.mkdir(exist_ok=True)
    audit_file = audit_dir / f"sample_{sample_num}.json"
    with open(audit_file, "w") as f:
        json.dump(sample_data, f, indent=2)
    print(f"Sample data saved to: {audit_file}")

    return sample_data

async def main():
    """Main audit loop"""
    sample_num = 1

    while True:
        sample_data = await run_audit_sample(sample_num)

        if sample_data is None:
            print("ERROR: Could not load sample data")
            return

        print("\nREADY FOR MANUAL REVIEW:")
        print("Please assess the 50 listings above on these criteria:")
        print("  1. PRICES - Are stored prices reasonable and match eBay?")
        print("  2. RELEVANCE - Are listings actually relevant to what they were found for?")
        print("  3. CLASSIFICATION - Are GEM/SUPER_GEM classifications justified?")
        print("  4. DEAL_SCORE - Does the deal score make sense?")
        print("  5. GEMS - Are identified gems truly the best in their category?")
        print("\nProvide findings as: defect_count, defect_descriptions")
        print("Type 'next' to continue to next sample, 'stop' to end audit")

        user_input = input("\n>>> ").strip().lower()

        if user_input == "stop":
            print("\nAudit loop ended by user")
            break
        elif user_input == "next":
            sample_num += 1
            continue
        else:
            print(f"Input received: {user_input}")
            sample_num += 1

if __name__ == "__main__":
    asyncio.run(main())
