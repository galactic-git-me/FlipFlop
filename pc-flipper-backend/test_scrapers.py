"""
Quick scraper test — run from the backend folder with:
  python test_scrapers.py

Prints how many listings each adapter finds.
"""
import asyncio
import sys
import os

# Make sure app imports work
sys.path.insert(0, os.path.dirname(__file__))

from app.services.scraper import scrape_ebay, scrape_gumtree


async def main():
    terms = ["gaming PC", "desktop computer i7"]

    print("=" * 60)
    print("Testing eBay scraper...")
    print("=" * 60)
    try:
        ebay = await scrape_ebay(terms, min_price=50, max_price=600)
        print(f"eBay returned {len(ebay)} listings")
        for l in ebay[:3]:
            print(f"  £{l.price:.0f}  {l.title[:60]}")
            print(f"       {l.url[:80]}")
    except Exception as e:
        print(f"eBay ERROR: {e}")

    print()
    print("=" * 60)
    print("Testing Gumtree scraper...")
    print("=" * 60)
    try:
        gt = await scrape_gumtree(terms, max_price=600)
        print(f"Gumtree returned {len(gt)} listings")
        for l in gt[:3]:
            print(f"  £{l.price:.0f}  {l.title[:60]}")
            print(f"       {l.url[:80]}")
    except Exception as e:
        print(f"Gumtree ERROR: {e}")


if __name__ == "__main__":
    asyncio.run(main())
