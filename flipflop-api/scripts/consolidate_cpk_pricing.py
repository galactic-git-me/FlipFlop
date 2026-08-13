"""
Run CPK consolidation to aggregate pricing across vendors.

Groups all listings by Canonical Product Key and aggregates their pricing,
creating a unified market baseline. This enables the scoring engine to use
cross-vendor data instead of EPID-only or single-listing prices.

Usage:
  python scripts/consolidate_cpk_pricing.py
"""
from __future__ import annotations

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.database import AsyncSessionLocal
from app.gem_radar.cpk_consolidation import consolidate_cpk_pricing

import structlog

log = structlog.get_logger(__name__)


async def main():
    async with AsyncSessionLocal() as db:
        try:
            aggregates = await consolidate_cpk_pricing(db)

            print()
            print("=" * 80)
            print(f"CPK Consolidation Complete!")
            print("=" * 80)
            print()
            print(f"Total CPK groups: {len(aggregates)}")
            print()

            # Statistics
            listing_counts = [a.listing_count for a in aggregates.values()]
            vendor_counts = [a.vendor_count for a in aggregates.values()]

            print("Consolidation Statistics:")
            print(f"  Listings per CPK:")
            print(f"    Min: {min(listing_counts)}")
            print(f"    Max: {max(listing_counts)}")
            print(f"    Avg: {sum(listing_counts) / len(listing_counts):.1f}")
            print()
            print(f"  Vendors per CPK:")
            print(f"    Min: {min(vendor_counts)}")
            print(f"    Max: {max(vendor_counts)}")
            print(f"    Avg: {sum(vendor_counts) / len(vendor_counts):.1f}")
            print(f"    Multi-vendor: {sum(1 for v in vendor_counts if v > 1)} ({100*sum(1 for v in vendor_counts if v > 1)//len(vendor_counts)}%)")
            print()

            # Top CPKs by listing count
            print("Top 10 CPK groups (by listing count):")
            for agg in sorted(aggregates.values(), key=lambda x: -x.listing_count)[:10]:
                print(f"  {agg.cpk} | {agg.brand} {agg.model[:30]} | {agg.listing_count} listings | {agg.vendor_count} vendors")
            print()

            print("Next: Re-score all listings using CPK-based pricing")
            print()

        except Exception as exc:
            log.error("consolidation_failed", error=str(exc))
            print(f"Error: {exc}")
            sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
