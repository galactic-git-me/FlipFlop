"""Offline backfill tool for Phase 1 of the CPK-driven market-price system.

Live ingestion (app/api/gem_radar.py's _submit_scan_body) already runs this
same logic per listing as the FlipFlopXtension submits it — see
app/gem_radar/cpk_pipeline.assign_cpk_and_accumulate_price. This script is
only for backfilling historical observations that predate that wiring (or
recovering after a full DB clear where only gem_radar_listing_observations
survived).
"""
from __future__ import annotations

import asyncio
import sys
from pathlib import Path
from datetime import datetime, timezone

sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import text
from app.database import AsyncSessionLocal
from app.gem_radar.cpk_pipeline import assign_cpk_and_accumulate_price

import structlog

log = structlog.get_logger(__name__)

BATCH_SIZE = 10


async def accumulate_cpk_prices():
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            text(
                """
                SELECT listing_id, title, category, condition_normalised, delivered_price
                FROM gem_radar_listing_observations
                ORDER BY listing_id
                """
            )
        )
        observations = result.fetchall()
        total = len(observations)
        print(f"Phase 1 backfill: accumulating CPK prices for {total} observations...")
        print()

        assigned_count = 0
        skipped_count = 0
        start_time = datetime.now(timezone.utc)

        for i in range(0, total, BATCH_SIZE):
            batch = observations[i : i + BATCH_SIZE]

            for row in batch:
                listing_id, title, category, condition, price = row[0], row[1], row[2], row[3], row[4]

                try:
                    cpk = await assign_cpk_and_accumulate_price(
                        db, listing_id, title, category, condition, price
                    )
                except Exception as exc:
                    log.error("phase1_backfill.failed", listing_id=listing_id, error=str(exc))
                    skipped_count += 1
                    continue

                if cpk is None:
                    skipped_count += 1
                else:
                    assigned_count += 1

            await db.commit()

            done = min(i + BATCH_SIZE, total)
            if done % 100 == 0 or done == total:
                elapsed = (datetime.now(timezone.utc) - start_time).total_seconds()
                rate = done / elapsed if elapsed > 0 else 0
                print(f"[{done:5d}/{total}] Assigned: {assigned_count:5d} | Skipped: {skipped_count:5d} | Rate: {rate:.1f}/s")

        elapsed = (datetime.now(timezone.utc) - start_time).total_seconds()
        print()
        print("=" * 80)
        print("Phase 1 Backfill Complete!")
        print("=" * 80)
        print(f"  Total observations: {total}")
        print(f"  CPK assigned: {assigned_count}")
        print(f"  Skipped (extraction failed): {skipped_count}")
        print(f"  Elapsed: {elapsed:.1f}s ({elapsed/60:.1f}m)")


async def main():
    try:
        await accumulate_cpk_prices()
    except KeyboardInterrupt:
        print("\nInterrupted")
        sys.exit(1)
    except Exception as exc:
        print(f"Error: {exc}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
