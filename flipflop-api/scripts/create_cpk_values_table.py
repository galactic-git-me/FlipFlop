"""Create persistent CPK values table and migrate existing data."""
from __future__ import annotations

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import text
from app.database import AsyncSessionLocal

import structlog

log = structlog.get_logger(__name__)


async def migrate_cpk_values():
    """Create cpk_values table and migrate existing CPK data from scored_listings."""
    async with AsyncSessionLocal() as db:
        print("Creating cpk_values table...")

        # Create table
        create_table_query = """
        CREATE TABLE IF NOT EXISTS gem_radar_listing_cpk (
            listing_id VARCHAR(50) PRIMARY KEY,
            cpk VARCHAR(64) NOT NULL,
            cpk_data JSONB,
            cpk_confidence FLOAT,
            extracted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """
        await db.execute(text(create_table_query))
        print("  Created gem_radar_listing_cpk table")

        # Migrate existing CPK values from scored_listings
        # First, clear any existing data
        await db.execute(text("TRUNCATE TABLE gem_radar_listing_cpk"))

        migrate_query = """
        INSERT INTO gem_radar_listing_cpk (listing_id, cpk, cpk_data, cpk_confidence)
        SELECT DISTINCT ON (listing_id) listing_id, cpk, cpk_data, cpk_confidence
        FROM gem_radar_scored_listings
        WHERE cpk IS NOT NULL
        """
        result = await db.execute(text(migrate_query))
        await db.commit()

        # Count migrated CPKs
        count_result = await db.execute(text("SELECT COUNT(*) FROM gem_radar_listing_cpk"))
        migrated_count = count_result.scalar()
        print(f"  Migrated {migrated_count} CPK values")

        # Get progress
        result = await db.execute(text("SELECT COUNT(*) FROM gem_radar_listing_cpk"))
        with_cpk = result.scalar()
        result = await db.execute(text("SELECT COUNT(*) FROM gem_radar_listing_observations"))
        total = result.scalar()
        pct = 100 * with_cpk // total if total > 0 else 0
        print(f"\nCPK Progress: {with_cpk}/{total} ({pct}%)")


async def main():
    try:
        await migrate_cpk_values()
        print("\nSuccess! CPK values are now persisted independently.")
    except Exception as exc:
        print(f"Error: {exc}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
