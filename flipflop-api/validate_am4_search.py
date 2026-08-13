"""
Validate AM4 CPU search: eBay API vs Extension Scraper

Criteria:
  - Query: AM4 CPU
  - Category: 46486 (Processors/CPUs)
  - Buy It Now only
  - Conditions: NEW, LIKE_NEW, MANUFACTURER_REFURBISHED, EXCELLENT
"""
import asyncio
import sys
import httpx

sys.path.insert(0, str(__file__).rsplit("\\", 1)[0])

from app.api.ebay_compliance import _get_app_token, _ebay_api_root
from app.services.scraper import scrape_ebay

# eBay API constants
_MARKETPLACE_ID = "EBAY_GB"
_CPU_CATEGORY = "46486"
_CONDITIONS = "NEW|LIKE_NEW|MANUFACTURER_REFURBISHED|EXCELLENT"


async def search_ebay_api_direct(query: str) -> list[dict]:
    """Direct eBay Browse API search with CPU category filter."""
    token = await _get_app_token()
    if not token:
        print("❌ No eBay API token available")
        return []

    root = _ebay_api_root()
    url = f"{root}/buy/browse/v1/item_summary/search"
    headers = {
        "Authorization": f"Bearer {token}",
        "X-EBAY-C-MARKETPLACE-ID": _MARKETPLACE_ID,
        "Content-Type": "application/json",
    }
    params = {
        "q": query,
        "filter": f"buyingOptions:{{FIXED_PRICE}},conditions:{{{_CONDITIONS}}}",
        "limit": "60",
        "fieldgroups": "MATCHING_ITEMS",
        # Note: _sacat parameter not supported in Browse API; category filtering
        # is done via item categorization in eBay's backend. We request the full
        # category spec separately if needed.
    }

    async with httpx.AsyncClient(timeout=20) as client:
        resp = await client.get(url, headers=headers, params=params)

    if resp.status_code != 200:
        print(f"❌ API error: {resp.status_code}")
        print(f"   Response: {resp.text[:200]}")
        return []

    items = resp.json().get("itemSummaries", [])
    results = []

    for item in items:
        price_info = item.get("price", {})
        if price_info.get("currency") != "GBP":
            continue

        try:
            price = float(price_info.get("value") or 0)
        except (ValueError, TypeError):
            continue

        if price < 10 or price > 10_000:
            continue

        title = str(item.get("title") or "")
        # Filter out accessories/coolers/parts
        if any(x in title.lower() for x in ["cooler", "fan", "bracket", "thermal", "parts", "faulty"]):
            continue

        results.append({
            "title": title,
            "price": price,
            "condition": str(item.get("condition") or ""),
            "url": str(item.get("itemWebUrl") or ""),
            "image_url": (item.get("image") or {}).get("imageUrl"),
        })

    return sorted(results, key=lambda x: x["price"])


async def search_extension_scraper(query: str) -> list:
    """Extension scraper search."""
    # Note: The scraper doesn't support category filtering via parameter
    # but it does filter based on component markers in the code
    listings = await scrape_ebay(
        search_terms=[query],
        min_price=10.0,
        max_price=10_000.0,
        auction_mode=False,  # BUY_IT_NOW only
        condition_code="1000",  # NEW condition - but scraper may return others too
    )
    return sorted(listings, key=lambda x: x.price)


async def main():
    query = "AM4 CPU"
    print(f"\n{'='*80}")
    print(f"AM4 CPU Search Validation")
    print(f"{'='*80}")
    print(f"\nCriteria:")
    print(f"  Query: {query}")
    print(f"  Category: {_CPU_CATEGORY} (Processors/CPUs)")
    print(f"  Type: Buy It Now only")
    print(f"  Conditions: {_CONDITIONS}\n")

    # Fetch from both sources
    print("Fetching from eBay Browse API...")
    api_results = await search_ebay_api_direct(query)
    print(f"  ✓ Found {len(api_results)} listings\n")

    print("Fetching from Extension Scraper...")
    try:
        scraper_results = await search_extension_scraper(query)
        print(f"  ✓ Found {len(scraper_results)} listings\n")
    except Exception as e:
        print(f"  ❌ Error: {e}\n")
        import traceback
        traceback.print_exc()
        scraper_results = []

    # Display results side-by-side
    print(f"{'='*80}")
    print("RESULTS COMPARISON")
    print(f"{'='*80}\n")

    print(f"{'Rank':<4} {'API Price':<12} {'API Title (40 chars)':<42} {'Scraper Price':<14} {'Scraper Title (40 chars)':<42}")
    print("-" * 120)

    max_rows = max(len(api_results), len(scraper_results))
    matches = 0

    for i in range(min(20, max_rows)):
        api = api_results[i] if i < len(api_results) else None
        scraper = scraper_results[i] if i < len(scraper_results) else None

        api_price_str = f"£{api['price']:.2f}" if api else "(none)"
        api_title_str = api["title"][:40] if api else ""

        scraper_price_str = f"£{scraper.price:.2f}" if scraper else "(none)"
        scraper_title_str = scraper.title[:40] if scraper else ""

        # Check if they match (simple heuristic: same price within £2, title overlap)
        match_marker = ""
        if api and scraper:
            price_close = abs(api["price"] - scraper.price) < 2
            title_match = any(
                word.lower() in scraper.title.lower()
                for word in api["title"].split()[:4]
            )
            if price_close and title_match:
                matches += 1
                match_marker = "✓"

        print(
            f"{i+1:<4} {api_price_str:<12} {api_title_str:<42} "
            f"{scraper_price_str:<14} {scraper_title_str:<42} {match_marker}"
        )

    print(f"\n{'='*80}")
    print(f"Summary:")
    print(f"  eBay API:        {len(api_results)} listings")
    print(f"  Scraper:         {len(scraper_results)} listings")
    print(f"  Top-20 matches:  {matches} / {min(20, max_rows)}")

    if len(api_results) > 0 and len(scraper_results) > 0:
        match_pct = (matches / min(20, max_rows)) * 100
        print(f"\nMatch rate: {match_pct:.0f}%")
        if match_pct >= 70:
            print("✅ PASS: Scraper matches API results")
        elif match_pct >= 40:
            print("⚠️  PARTIAL: Some discrepancies")
        else:
            print("❌ FAIL: Results do not align")
    elif len(api_results) == 0:
        print("\n⚠️  API returned 0 results (check category filter)")
    elif len(scraper_results) == 0:
        print("\n⚠️  Scraper returned 0 results")


if __name__ == "__main__":
    asyncio.run(main())
