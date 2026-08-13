"""One-off schema setup for the CPK market-price two-phase system:
- Creates gem_radar_listing_cpk / gem_radar_cpk_listing_price /
  gem_radar_cpk_market_price (new ORM models, via create_all).
- ALTERs gem_radar_scored_listings to add the columns phase 2 writes to
  (market_lower_price, market_median_price, market_upper_price, pct_offset,
  recommendation) — create_all only creates missing tables, it never adds
  columns to a table that already exists.
- ALTERs app_settings to add the deal_* threshold columns for the same
  reason.

Safe to re-run — every statement is idempotent (IF NOT EXISTS / ADD COLUMN
IF NOT EXISTS).
"""
from __future__ import annotations

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import text
from app.database import AsyncSessionLocal, engine, Base
from app import models as _models  # noqa: F401  registers all ORM models


async def setup_schema():
    print("Creating any missing tables (gem_radar_listing_cpk, gem_radar_cpk_listing_price, gem_radar_cpk_market_price, ...)...")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    print("  Done.")

    async with AsyncSessionLocal() as db:
        print("\nAdding new columns to gem_radar_scored_listings...")
        await db.execute(text("""
            ALTER TABLE gem_radar_scored_listings
                ADD COLUMN IF NOT EXISTS market_lower_price FLOAT,
                ADD COLUMN IF NOT EXISTS market_median_price FLOAT,
                ADD COLUMN IF NOT EXISTS market_upper_price FLOAT,
                ADD COLUMN IF NOT EXISTS pct_offset FLOAT,
                ADD COLUMN IF NOT EXISTS recommendation VARCHAR(30)
        """))
        print("  Done.")

        print("\nAdding new deal_* threshold columns to app_settings...")
        await db.execute(text("""
            ALTER TABLE app_settings
                ADD COLUMN IF NOT EXISTS deal_market_price_source VARCHAR(10) DEFAULT 'median',
                ADD COLUMN IF NOT EXISTS deal_super_gem_threshold_pct FLOAT DEFAULT -20.0,
                ADD COLUMN IF NOT EXISTS deal_gem_threshold_pct FLOAT DEFAULT -15.0,
                ADD COLUMN IF NOT EXISTS deal_ok_deal_threshold_pct FLOAT DEFAULT -5.0,
                ADD COLUMN IF NOT EXISTS deal_average_deal_threshold_pct FLOAT DEFAULT 10.0
        """))
        print("  Done.")

        await db.commit()

    print("\nSchema setup complete.")


async def main():
    try:
        await setup_schema()
    except Exception as exc:
        print(f"Error: {exc}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
