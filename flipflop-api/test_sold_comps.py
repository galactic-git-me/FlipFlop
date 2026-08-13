#!/usr/bin/env python
"""
Quick test of LiveSoldCompsAdapter to verify eBay sold comps scraping works.

Usage:
    python test_sold_comps.py "intel i7 13700" used
    python test_sold_comps.py "nvidia rtx 4070" new
"""
import asyncio
import sys
import structlog
from app.gem_radar.adapters.sold_comps import LiveSoldCompsAdapter

structlog.configure(
    processors=[structlog.processors.JSONRenderer()],
)
log = structlog.get_logger(__name__)


async def test_scrape():
    """Test the LiveSoldCompsAdapter on a query."""
    if len(sys.argv) < 2:
        query = "Intel Core i7-13700K"
        condition = "used"
    else:
        query = sys.argv[1]
        condition = sys.argv[2] if len(sys.argv) > 2 else "used"

    print(f"\n[SEARCH] Testing sold comps scrape for: '{query}' ({condition})")
    print("-" * 70)

    adapter = LiveSoldCompsAdapter()
    result = await adapter.fetch(query, condition)

    if result.available:
        print(f"[SUCCESS] Found {len(result.comps)} sold listings:\n")
        for i, comp in enumerate(result.comps, 1):
            print(f"  {i}. £{comp.price:.2f} ({comp.condition})")
            if comp.url:
                print(f"     URL: {comp.url}")
        return True
    else:
        print(f"[ERROR] {result.unavailable_reason}")
        return False


if __name__ == "__main__":
    success = asyncio.run(test_scrape())
    sys.exit(0 if success else 1)
