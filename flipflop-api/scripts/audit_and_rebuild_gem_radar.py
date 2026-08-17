"""Backup-first Gem Radar cleanup and classification rebuild.

Dry-run is the default.  --apply creates timestamped database backup tables,
quarantines invalid CPK assignments, consolidates scored rows, then runs the
new opportunity classifier. Observation and demand ledgers are retained as
history; they are not destructive duplicates.
"""
from __future__ import annotations
import argparse
import asyncio
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from sqlalchemy import text
from app.database import AsyncSessionLocal
from app.gem_radar.phase2_runner import run_phase2_classification


INVALID_CPK_SQL = """
    cpk_data IS NULL OR cpk_data->>'category' IS NULL OR cpk_data->>'brand' IS NULL OR cpk_data->>'model' IS NULL
    OR cpk_data->>'category' NOT IN ('cpu','gpu','motherboard','ram','ssd','psu','cooler','case','fan')
    OR LOWER(cpk_data->>'brand') LIKE '%brand name%'
    OR LOWER(cpk_data->>'model') LIKE '%model-id%'
"""


async def run(apply: bool) -> None:
    async with AsyncSessionLocal() as db:
        counts = (await db.execute(text(f"""
            SELECT
              (SELECT COUNT(*) FROM gem_radar_scored_listings) scored_rows,
              (SELECT COUNT(DISTINCT listing_id) FROM gem_radar_scored_listings) unique_scored,
              (SELECT COUNT(*) FROM gem_radar_listing_cpk WHERE {INVALID_CPK_SQL}) invalid_cpks
        """))).one()
        print({"scored_rows": counts[0], "unique_scored": counts[1], "duplicate_scored": counts[0] - counts[1], "invalid_cpks": counts[2], "apply": apply})
        if not apply:
            return

        suffix = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        await db.execute(text(f"CREATE TABLE gem_radar_scored_backup_{suffix} AS TABLE gem_radar_scored_listings"))
        await db.execute(text(f"CREATE TABLE gem_radar_cpk_backup_{suffix} AS TABLE gem_radar_listing_cpk"))
        await db.execute(text(f"CREATE TABLE gem_radar_cpk_price_backup_{suffix} AS TABLE gem_radar_cpk_listing_price"))
        await db.execute(text(f"""
            DELETE FROM gem_radar_cpk_listing_price p USING gem_radar_listing_cpk c
            WHERE p.listing_id = c.listing_id AND ({INVALID_CPK_SQL})
        """))
        await db.execute(text(f"DELETE FROM gem_radar_listing_cpk WHERE {INVALID_CPK_SQL}"))
        await db.execute(text("""
            DELETE FROM gem_radar_scored_listings older USING gem_radar_scored_listings newer
            WHERE older.listing_id = newer.listing_id
              AND (older.scored_at, older.id) < (newer.scored_at, newer.id)
        """))
        await db.commit()
        result = await run_phase2_classification(db)
        print({"backup_suffix": suffix, "classification_counts": result.classification_counts,
               "classified": result.classified_count, "insufficient_market": result.unsettled_count})


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    asyncio.run(run(args.apply))
