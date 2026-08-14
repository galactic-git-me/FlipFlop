"""One-off: compute the % offset distribution across every settled CPK-tagged
listing (same population run_phase2_classification just classified), then
report what super_gem/gem threshold values would put the top 10% of deals
into SUPER_GEM and the next 20% into GEM -- answering "what should the
thresholds be" directly from the data instead of guessing.
"""
from __future__ import annotations

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import text

from app.database import AsyncSessionLocal
from app.gem_radar.cpk_market import get_market_price_with_hierarchy_fallback
from app.gem_radar.deal_classification import load_deal_thresholds, market_price_for_source, pct_offset


async def main():
    async with AsyncSessionLocal() as db:
        thresholds = await load_deal_thresholds(db)
        print(f"market_price_source: {thresholds.market_price_source}")

        result = await db.execute(
            text(
                """
                SELECT lo.delivered_price, cpk.cpk
                FROM gem_radar_listing_observations lo
                JOIN gem_radar_listing_cpk cpk ON lo.listing_id = cpk.listing_id
                ORDER BY lo.listing_id
                """
            )
        )
        rows = result.fetchall()

        offsets: list[float] = []
        for delivered_price, cpk in rows:
            market = await get_market_price_with_hierarchy_fallback(db, cpk)
            if market is None:
                continue
            market_price = market_price_for_source(market, thresholds.market_price_source)
            offsets.append(pct_offset(delivered_price, market_price))

        offsets.sort()
        n = len(offsets)
        print(f"settled/classified offsets collected: {n}")

        def pct(p: float) -> float:
            idx = min(n - 1, max(0, round(p * (n - 1))))
            return offsets[idx]

        print(f"  p1  (top 1%):  offset <= {pct(0.01):.2f}%")
        print(f"  p5  (top 5%):  offset <= {pct(0.05):.2f}%")
        print(f"  p10 (top 10%): offset <= {pct(0.10):.2f}%   <- proposed super_gem_pct")
        print(f"  p20:           offset <= {pct(0.20):.2f}%")
        print(f"  p30 (top 30%): offset <= {pct(0.30):.2f}%   <- proposed gem_pct (cumulative top 30%)")
        print(f"  p50 (median):  offset <= {pct(0.50):.2f}%")
        print(f"  p70:           offset <= {pct(0.70):.2f}%")
        print(f"  p90:           offset <= {pct(0.90):.2f}%")

        print()
        print(f"Current thresholds: super_gem={thresholds.super_gem_pct}%, gem={thresholds.gem_pct}%, "
              f"ok_deal={thresholds.ok_deal_pct}%, average_deal={thresholds.average_deal_pct}%")

        current_super = sum(1 for o in offsets if o <= thresholds.super_gem_pct)
        current_gem = sum(1 for o in offsets if thresholds.super_gem_pct < o <= thresholds.gem_pct)
        print(f"With current thresholds: SUPER_GEM={current_super} ({100*current_super/n:.1f}%), "
              f"GEM={current_gem} ({100*current_gem/n:.1f}%)")


asyncio.run(main())
