"""
Standalone AM4 CPU validation - no app dependencies needed.
Compares eBay API directly vs Extension scraper.
"""
import asyncio
import httpx
import os
import base64
from pathlib import Path

# Read environment for eBay API credentials
EBAY_APP_ID = os.getenv("EBAY_APP_ID", "").strip()
EBAY_CLIENT_SECRET = os.getenv("EBAY_CLIENT_SECRET", "").strip()

if not EBAY_APP_ID or not EBAY_CLIENT_SECRET:
    print("[ERROR] EBAY_APP_ID and EBAY_CLIENT_SECRET not set in environment")
    print("   Set them and try again:")
    print("   $env:EBAY_APP_ID = 'your-id'")
    print("   $env:EBAY_CLIENT_SECRET = 'your-secret'")
    exit(1)


async def get_ebay_token() -> str | None:
    """Get eBay app token via OAuth."""
    creds = f"{EBAY_APP_ID}:{EBAY_CLIENT_SECRET}".encode("utf-8")
    basic = base64.b64encode(creds).decode("ascii")

    headers = {
        "Authorization": f"Basic {basic}",
        "Content-Type": "application/x-www-form-urlencoded",
    }
    data = {"grant_type": "client_credentials", "scope": "https://api.ebay.com/oauth/api_scope"}

    async with httpx.AsyncClient(timeout=20) as client:
        resp = await client.post("https://api.ebay.com/identity/v1/oauth2/token", data=data, headers=headers)

    if resp.status_code != 200:
        print(f"[ERROR] Token error: {resp.status_code}")
        print(f"   {resp.text[:200]}")
        return None

    return resp.json().get("access_token")


async def search_ebay_api(token: str) -> list[dict]:
    """Search eBay Browse API for AM4 CPU."""
    url = "https://api.ebay.com/buy/browse/v1/item_summary/search"
    headers = {
        "Authorization": f"Bearer {token}",
        "X-EBAY-C-MARKETPLACE-ID": "EBAY_GB",
        "Content-Type": "application/json",
    }
    params = {
        "q": "AM4 CPU",
        "filter": "buyingOptions:{FIXED_PRICE},conditions:{NEW|LIKE_NEW|MANUFACTURER_REFURBISHED|EXCELLENT}",
        "limit": "60",
        "fieldgroups": "MATCHING_ITEMS",
    }

    async with httpx.AsyncClient(timeout=20) as client:
        resp = await client.get(url, headers=headers, params=params)

    if resp.status_code != 200:
        print(f"[ERROR] API error: {resp.status_code}")
        return []

    items = resp.json().get("itemSummaries", [])
    results = []

    for item in items:
        try:
            price_info = item.get("price", {})
            if price_info.get("currency") != "GBP":
                continue

            price = float(price_info.get("value") or 0)
            if price < 10 or price > 10_000:
                continue

            title = str(item.get("title") or "")
            # Skip accessories
            if any(x in title.lower() for x in ["cooler", "fan", "bracket", "thermal", "parts", "faulty"]):
                continue

            results.append({
                "title": title,
                "price": price,
                "condition": str(item.get("condition") or ""),
                "url": str(item.get("itemWebUrl") or ""),
            })
        except Exception as e:
            continue

    return sorted(results, key=lambda x: x["price"])


async def main():
    print(f"\n{'='*100}")
    print(f"AM4 CPU Search: eBay API vs Extension Scraper")
    print(f"{'='*100}\n")
    print("Criteria:")
    print("  • Query: AM4 CPU")
    print("  • Category: 46486 (Processors)")
    print("  • Type: Buy It Now only")
    print("  • Conditions: NEW, LIKE_NEW, MANUFACTURER_REFURBISHED, EXCELLENT\n")

    # Get token
    print("Getting eBay API token...")
    token = await get_ebay_token()
    if not token:
        return

    print("[OK] Token obtained\n")

    # Search API
    print("Searching eBay Browse API...")
    api_results = await search_ebay_api(token)
    print(f"[OK] Found {len(api_results)} listings\n")

    # Display results
    print(f"{'Rank':<5} {'Price':<10} {'Condition':<20} {'Title (60 chars)':<60}")
    print("-" * 100)

    for i, item in enumerate(api_results[:20]):
        print(f"{i+1:<5} £{item['price']:<9.2f} {item['condition']:<20} {item['title'][:60]:<60}")

    print(f"\n[OK] eBay API: {len(api_results)} total results")
    print("\nNow compare these with your extension scraper results.")
    print("Take note of: titles, prices, and conditions returned.")


if __name__ == "__main__":
    asyncio.run(main())
