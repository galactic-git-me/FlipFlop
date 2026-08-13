"""Extract CPK for ALL listings to identify products EPID misses."""
from __future__ import annotations

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import asyncpg
from app.gem_radar.cpk_extractor import extract_cpk
import json

import structlog

log = structlog.get_logger(__name__)


async def extract_all_cpk():
    """Extract CPK for all scored listings regardless of price status."""
    conn = await asyncpg.connect("postgresql://flipper:flipper@127.0.0.1:5432/pcflipper")

    try:
        # Create persistent CPK table if it doesn't exist
        await conn.execute('''
            CREATE TABLE IF NOT EXISTS gem_radar_listing_cpk (
                listing_id VARCHAR(50) PRIMARY KEY,
                cpk VARCHAR(64) NOT NULL,
                cpk_data JSONB,
                cpk_confidence FLOAT,
                extracted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        # Get ALL listings without CPK (check both tables)
        listings = await conn.fetch('''
            SELECT DISTINCT gs.listing_id, gs.title, gs.category, gs.condition
            FROM gem_radar_scored_listings gs
            LEFT JOIN gem_radar_listing_cpk cpk ON gs.listing_id = cpk.listing_id
            WHERE cpk.listing_id IS NULL
            ORDER BY gs.listing_id
        ''')

        print(f"Extracting CPK for {len(listings)} listings...")
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
                        listing_id = row['listing_id']
                        # Store in persistent CPK table
                        await conn.execute(
                            '''INSERT INTO gem_radar_listing_cpk (listing_id, cpk, cpk_data, cpk_confidence)
                               VALUES ($1, $2, $3, $4)
                               ON CONFLICT (listing_id) DO UPDATE SET
                                 cpk = $2,
                                 cpk_data = $3,
                                 cpk_confidence = $4,
                                 updated_at = CURRENT_TIMESTAMP''',
                            listing_id,
                            cpk_data.cpk,
                            json.dumps(cpk_data.to_dict()),
                            cpk_data.confidence,
                        )
                        # Also update scored_listings for compatibility
                        await conn.execute(
                            '''UPDATE gem_radar_scored_listings
                               SET cpk = $1, cpk_data = $2, cpk_confidence = $3
                               WHERE listing_id = $4''',
                            cpk_data.cpk,
                            json.dumps(cpk_data.to_dict()),
                            cpk_data.confidence,
                            listing_id
                        )
                        extracted += 1
                    else:
                        skipped += 1

            if batch_end % 500 == 0 or batch_end == len(listings):
                pct = 100 * extracted // (extracted + skipped) if (extracted + skipped) > 0 else 0
                print(f"  [{batch_end}/{len(listings)}] Extracted: {extracted}, Skipped: {skipped}, Rate: {pct}%")

        print(f"\nComplete: {extracted} extracted ({100*extracted//(extracted+skipped)}%), {skipped} skipped")

    finally:
        await conn.close()


async def main():
    try:
        await extract_all_cpk()
    except Exception as exc:
        print(f"Error: {exc}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
