"""
Batch extract Canonical Product Keys (CPK) for all scored listings.

Processes all 11.8k+ listings, extracts structured product data via Qwen2,
generates deterministic CPKs, and stores in database for cross-vendor consolidation.

Usage:
  python scripts/batch_extract_cpk.py
  python scripts/batch_extract_cpk.py --limit 100  # Test on first 100
"""
from __future__ import annotations

import asyncio
import sys
import argparse
from datetime import datetime, timezone
from pathlib import Path
import json

# Add parent directory to path so imports work
sys.path.insert(0, str(Path(__file__).parent.parent))

import asyncpg
import structlog
from sqlalchemy import text

from app.database import AsyncSessionLocal
from app.gem_radar.cpk_extractor import extract_cpk

log = structlog.get_logger(__name__)


async def batch_extract_cpk(limit: int | None = None, batch_size: int = 5):
    """
    Extract CPK for all unprocessed scored listings.

    Args:
        limit: Max listings to process (None = all)
        batch_size: Listings to process in parallel
    """
    # Get database URL from config
    from app.database import _database_url
    # Convert async URL to sync for asyncpg
    conn_url = _database_url.replace("postgresql+asyncpg://", "postgresql://")
    conn = await asyncpg.connect(conn_url)

    try:
        # Get unprocessed listings
        query = "SELECT listing_id, title, category, condition FROM gem_radar_scored_listings WHERE cpk IS NULL ORDER BY scored_at DESC"
        if limit:
            query += f" LIMIT {limit}"

        listings = await conn.fetch(query)

        if not listings:
            print("All listings already have CPK. Nothing to do.")
            return

        total = len(listings)
        print(f"Processing {total} listings ({batch_size} in parallel)...")
        print()

        processed = 0
        skipped = 0
        errors = 0
        start_time = datetime.now(timezone.utc)

        # Process in batches
        for batch_start in range(0, total, batch_size):
            batch_end = min(batch_start + batch_size, total)
            batch = listings[batch_start:batch_end]

            # Extract CPK in parallel for this batch
            tasks = [
                extract_cpk(row["title"], row["category"], row["condition"])
                for row in batch
            ]
            results = await asyncio.gather(*tasks)

            # Update database
            for row, cpk_data in zip(batch, results):
                listing_id = row["listing_id"]
                try:
                    if cpk_data:
                        await conn.execute(
                            """
                            UPDATE gem_radar_scored_listings
                            SET cpk = $1, cpk_data = $2, cpk_confidence = $3
                            WHERE listing_id = $4
                            """,
                            cpk_data.cpk,
                            json.dumps(cpk_data.to_dict()),
                            cpk_data.confidence,
                            listing_id,
                        )
                        processed += 1
                    else:
                        skipped += 1
                except Exception as exc:
                    log.error("batch_extract_cpk.db_error", listing_id=listing_id, error=str(exc))
                    errors += 1

            # Progress
            progress = batch_end
            elapsed = (datetime.now(timezone.utc) - start_time).total_seconds()
            rate = progress / elapsed if elapsed > 0 else 0
            eta_remaining = (total - progress) / rate if rate > 0 else 0

            print(f"[{progress:5d}/{total}] Extracted: {processed:5d} | Skipped: {skipped:5d} | Errors: {errors:2d} | Rate: {rate:.1f}/s | ETA: {eta_remaining:.0f}s")

        print()
        print("=" * 80)
        print(f"Complete!")
        print(f"  Extracted: {processed} ({100*processed//total if total > 0 else 0}%)")
        print(f"  Skipped: {skipped} (low confidence or unrecognizable)")
        print(f"  Errors: {errors}")
        print(f"  Elapsed: {elapsed:.1f}s")
        print()
        print("Next: Consolidate by CPK and aggregate pricing")

    finally:
        await conn.close()


async def main():
    parser = argparse.ArgumentParser(
        description="Batch extract Canonical Product Keys (CPK) for all scored listings"
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Max listings to process (None = all)",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=50,
        help="Parallel batch size (default 50)",
    )
    args = parser.parse_args()

    try:
        await batch_extract_cpk(limit=args.limit, batch_size=args.batch_size)
    except KeyboardInterrupt:
        print("\nInterrupted by user")
        sys.exit(1)
    except Exception as exc:
        print(f"Error: {exc}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
