#!/usr/bin/env python
"""Verify scraped prices against actual eBay listings."""
import re
from sqlalchemy import create_engine, text
import httpx

engine = create_engine("postgresql://flipper:flipper@127.0.0.1:5432/pcflipper")

# Get some questionable listings
with engine.connect() as conn:
    query = text("""
    SELECT DISTINCT listing_id, title, delivered_price
    FROM gem_radar_listing_observations
    WHERE delivered_price < 20
      AND source = 'ebay'
      AND (title ILIKE '%cpu%' OR title ILIKE '%gpu%')
    LIMIT 5
    """)

    result = conn.execute(query)
    listings = result.fetchall()

print("🔍 VERIFYING PRICES AGAINST ACTUAL eBay LISTINGS:\n")
print("="*80)

for listing_id, title, scraped_price in listings:
    ebay_url = f"https://www.ebay.co.uk/itm/{listing_id}"
    print(f"\n📦 Listing: {listing_id}")
    print(f"   Title: {title[:60]}...")
    print(f"   Scraped Price: £{scraped_price:.2f}")
    print(f"   eBay URL: {ebay_url}")

    try:
        # Try to fetch the eBay page
        response = httpx.get(ebay_url, timeout=10, follow_redirects=True)

        # Look for price in the page
        if response.status_code == 200:
            # Try to find price patterns in the HTML
            price_patterns = [
                r'price["\']?\s*:\s*["\']?([\d,]+\.?\d*)',
                r'\$[\d,]+\.?\d*',
                r'£[\d,]+\.?\d*',
                r'(<span[^>]*class=["\']?price["\']?[^>]*>[\s\S]*?</span>)',
            ]

            found_price = None
            for pattern in price_patterns:
                matches = re.findall(pattern, response.text, re.IGNORECASE)
                if matches:
                    found_price = matches[0]
                    break

            if found_price:
                print(f"   ✓ Found price on page: {found_price}")
            else:
                print(f"   ⚠️  Could not extract price from page (page loaded)")
        else:
            print(f"   ❌ Page returned {response.status_code}")
    except Exception as e:
        print(f"   ❌ Error fetching: {str(e)[:60]}")

print("\n" + "="*80)
print("\nNote: This is a basic verification. For thorough price checking,")
print("we need to compare scraped prices with actual eBay listing pages.")
