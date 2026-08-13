"""
Validation script: Compare eBay Browse API vs Extension Scraper results.

Fetches AM4 CPU listings from both sources and compares them to ensure
scraper results match API results (which are authoritative).
"""
import asyncio
import sys
from typing import Optional

# Add app directory to path
sys.path.insert(0, str(__file__).rsplit("\\", 1)[0])

from app.services.ebay_browse import _search as ebay_api_search
from app.api.ebay_compliance import _get_app_token
from app.services.scraper import scrape_ebay


async def validate():
    """Compare eBay API vs scraper for AM4 CPU search."""
    query = "AM4 CPU"
    print(f"\n{'='*70}")
    print(f"VALIDATION: AM4 CPU Search (eBay API vs Extension Scraper)")
    print(f"{'='*70}\n")

    # Get eBay API token
    token = await _get_app_token()
    if not token:
        print("❌ FAILED: Could not get eBay API token")
        print("   Check EBAY_APP_ID and EBAY_CLIENT_SECRET in environment")
        return False

    print(f"✓ eBay API token obtained\n")

    # Fetch from eBay API (new condition)
    print("Fetching from eBay Browse API (NEW condition)...")
    api_new = await ebay_api_search(token, query, "NEW|LIKE_NEW|MANUFACTURER_REFURBISHED", limit=50)
    print(f"  Found: {len(api_new)} listings")

    # Fetch from eBay API (used condition)
    print("Fetching from eBay Browse API (USED condition)...")
    api_used = await ebay_api_search(token, query, "USED|EXCELLENT|VERY_GOOD|GOOD|ACCEPTABLE", limit=50)
    print(f"  Found: {len(api_used)} listings")

    api_total = len(api_new) + len(api_used)
    api_listings = api_new + api_used
    print(f"  Total from API: {api_total} listings\n")

    # Fetch from Extension Scraper
    print("Fetching from Extension Scraper...")
    try:
        # Use same price range as API: £10-£10k
        scraper_listings = await scrape_ebay(
            search_terms=[query],
            min_price=10.0,
            max_price=10_000.0,
            auction_mode=False,
        )
        print(f"  Found: {len(scraper_listings)} listings\n")
    except Exception as e:
        print(f"  ❌ Scraper error: {e}\n")
        import traceback
        traceback.print_exc()
        scraper_listings = []

    # COMPARISON REPORT
    print(f"{'='*70}")
    print("COMPARISON REPORT")
    print(f"{'='*70}\n")

    if not api_listings and not scraper_listings:
        print("⚠️  Both sources returned empty results — cannot validate")
        return None

    if not api_listings:
        print("❌ eBay API returned 0 results (API issue)")
        return False

    if not scraper_listings:
        print("❌ Extension scraper returned 0 results (scraper issue)")
        return False

    # Compare counts
    count_match = len(api_listings) == len(scraper_listings)
    print(f"Count match: {count_match}")
    print(f"  eBay API:     {len(api_listings)} listings")
    print(f"  Scraper:      {len(scraper_listings)} listings")
    if not count_match:
        print(f"  Difference:   {abs(len(api_listings) - len(scraper_listings))} listings\n")
    else:
        print()

    # Compare top 10 by price (normalize to title keywords)
    print(f"Top 10 Price Comparison (API vs Scraper):\n")
    print(f"{'Rank':<5} {'API Price':<12} {'API Title (first 40 chars)':<42} {'Scraper Price':<14} {'Scraper Title (first 40 chars)':<42}")
    print("-" * 130)

    api_sorted = sorted(api_listings, key=lambda x: x["price"])[:10]
    scraper_sorted = sorted(scraper_listings, key=lambda x: x.price)[:10]

    max_len = max(len(api_sorted), len(scraper_sorted))
    matches = 0
    for i in range(max_len):
        api_item = api_sorted[i] if i < len(api_sorted) else None
        scraper_item = scraper_sorted[i] if i < len(scraper_sorted) else None

        if api_item and scraper_item:
            # Simple match: title contains key keyword from the other
            api_title = api_item["title"].lower()
            scraper_title = scraper_item.title.lower()
            title_match = any(word in scraper_title for word in api_title.split()[:3])
            price_close = abs(api_item["price"] - scraper_item.price) < 5  # Within £5

            if title_match and price_close:
                matches += 1
                status = "✓"
            else:
                status = "⚠️ "

            print(
                f"{i+1:<5} £{api_item['price']:<11.2f} {api_item['title'][:40]:<42} "
                f"£{scraper_item.price:<13.2f} {scraper_item.title[:40]:<42} {status}"
            )
        elif api_item:
            print(f"{i+1:<5} £{api_item['price']:<11.2f} {api_item['title'][:40]:<42} (no scraper result)")
        elif scraper_item:
            print(f"{i+1:<5} (no API result) {'':<42} £{scraper_item.price:<13.2f} {scraper_item.title[:40]:<42}")

    match_pct = (matches / max_len * 100) if max_len > 0 else 0
    print(f"\nTop-10 match rate: {matches}/{max_len} ({match_pct:.0f}%)\n")

    # Overall verdict
    print(f"{'='*70}")
    if match_pct >= 70:
        print("✅ PASS: Scraper results closely match eBay API (>70% match rate)")
        return True
    elif match_pct >= 40:
        print("⚠️  PARTIAL: Some mismatches detected (40-70% match rate)")
        return None
    else:
        print("❌ FAIL: Results do not match (scraper extraction issue)")
        return False


if __name__ == "__main__":
    result = asyncio.run(validate())
    sys.exit(0 if result is True else 1)
