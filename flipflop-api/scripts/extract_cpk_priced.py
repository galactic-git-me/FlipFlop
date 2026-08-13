"""Extract CPK for priced listings using parallel batching."""
from __future__ import annotations

import asyncio
import sys
import json
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import asyncpg
from app.gem_radar.cpk_extractor import extract_cpk

import structlog

log = structlog.get_logger(__name__)


async def extract_cpk_batch():
    """Extract CPK for priced listings with parallelism."""
    conn = await asyncpg.connect("postgresql://flipper:flipper@127.0.0.1:5432/pcflipper")

    try:
        # Get priced listings without CPK
        listings = await conn.fetch('''
            SELECT listing_id, title, category, condition
            FROM gem_radar_scored_listings
            WHERE (market_new_price IS NOT NULL OR market_used_price IS NOT NULL)
              AND cpk IS NULL
            ORDER BY listing_id
        ''')

        print(f"Extracting CPK for {len(listings)} listings (parallel batch_size=10)...")

        extracted = 0
        skipped = 0
        batch_size = 10

        for batch_start in range(0, len(listings), batch_size):
            batch_end = min(batch_start + batch_size, len(listings))
            batch = listings[batch_start:batch_end]

            # Extract in parallel
            tasks = [extract_cpk(row['title'], row['category'], row['condition']) for row in batch]
            results = await asyncio.gather(*tasks)

            # Save results in transaction
            async with conn.transaction():
                for row, cpk_data in zip(batch, results):
                    if cpk_data:
                        await conn.execute(
                            '''UPDATE gem_radar_scored_listings
                               SET cpk = $1, cpk_data = $2, cpk_confidence = $3
                               WHERE listing_id = $4''',
                            cpk_data.cpk,
                            json.dumps(cpk_data.to_dict()),
                            cpk_data.confidence,
                            row['listing_id']
                        )
                        extracted += 1
                    else:
                        skipped += 1

            if batch_end % 100 == 0 or batch_end == len(listings):
                print(f"  [{batch_end}/{len(listings)}] Extracted: {extracted}, Skipped: {skipped}")

        print(f"\nComplete: {extracted} extracted, {skipped} skipped")

    finally:
        await conn.close()


async def main():
    try:
        await extract_cpk_batch()
    except Exception as exc:
        print(f"Error: {exc}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
