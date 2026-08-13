"""
Test AM5 CPU search (the one that's supposedly hanging).
"""
import asyncio
import httpx
import os
import base64

EBAY_APP_ID = os.getenv("EBAY_APP_ID", "MichaelC-FlipFlop-PRD-7183f64d5-21fdc8a9").strip()
EBAY_CLIENT_SECRET = os.getenv("EBAY_CLIENT_SECRET", "PRD-183f64d59369-d90f-457d-b12e-8fe6").strip()


async def get_ebay_token() -> str | None:
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
        return None
    return resp.json().get("access_token")


async def search_ebay_api(token: str, query: str) -> list[dict]:
    """Search with the exact criteria from the request."""
    url = "https://api.ebay.com/buy/browse/v1/item_summary/search"
    headers = {
        "Authorization": f"Bearer {token}",
        "X-EBAY-C-MARKETPLACE-ID": "EBAY_GB",
        "Content-Type": "application/json",
    }
    # Exact criteria: Buy It Now, NEW, OPENED_UNUSED, REFURBISHED, EXCELLENT
    params = {
        "q": query,
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
            if any(x in title.lower() for x in ["cooler", "fan", "bracket", "thermal", "parts", "faulty"]):
                continue
            results.append({
                "title": title,
                "price": price,
                "condition": str(item.get("condition") or ""),
                "url": str(item.get("itemWebUrl") or ""),
            })
        except:
            continue

    return sorted(results, key=lambda x: x["price"])


async def main():
    print("\nTesting both searches:\n")

    token = await get_ebay_token()
    if not token:
        print("[ERROR] Could not get eBay token")
        return

    for query in ["AM4 CPU", "AM5 CPU"]:
        results = await search_ebay_api(token, query)
        print(f"{query}:")
        print(f"  Found: {len(results)} listings")
        if results:
            print(f"  Price range: £{results[0]['price']:.2f} - £{results[-1]['price']:.2f}")
            print(f"  Sample: {results[0]['title'][:60]}")
        print()


if __name__ == "__main__":
    asyncio.run(main())
