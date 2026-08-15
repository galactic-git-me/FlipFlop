#!/usr/bin/env python
"""Backfill search_run_id for historical observations that lack it."""
from sqlalchemy import create_engine, text
from datetime import datetime
import uuid

engine = create_engine("postgresql://flipper:flipper@127.0.0.1:5432/pcflipper")

print("🔄 Backfilling search_run_id for historical observations...\n")

with engine.connect() as conn:
    # Find observations without search_run_id
    check_query = text("""
    SELECT COUNT(*) as missing_count
    FROM gem_radar_listing_observations
    WHERE search_run_id IS NULL
    """)

    result = conn.execute(check_query)
    missing_count = result.scalar()

    print(f"Observations missing search_run_id: {missing_count:,}")

    if missing_count == 0:
        print("✓ No backfill needed - all observations have search_run_id")
    else:
        # Group by date and search_query to create logical run IDs
        backfill_query = text("""
        WITH missing_obs AS (
            SELECT
                listing_id,
                DATE(observed_at) as obs_date,
                search_query,
                category,
                ROW_NUMBER() OVER (
                    PARTITION BY DATE(observed_at), COALESCE(search_query, category)
                    ORDER BY observed_at
                ) as seq
            FROM gem_radar_listing_observations
            WHERE search_run_id IS NULL
        )
        UPDATE gem_radar_listing_observations obs
        SET search_run_id = 'backfill-' || mo.obs_date || '-' ||
                           COALESCE(mo.search_query, mo.category, 'unknown') || '-' ||
                           LPAD(mo.seq::text, 4, '0')
        FROM missing_obs mo
        WHERE obs.listing_id = mo.listing_id
          AND obs.search_run_id IS NULL
        """)

        result = conn.execute(backfill_query)
        conn.commit()

        print(f"✓ Backfilled {result.rowcount:,} observations")

# Verify
print("\n" + "="*80)
print("Verification:\n")

with engine.connect() as conn:
    verify_query = text("""
    SELECT
        COUNT(*) as total,
        COUNT(CASE WHEN search_run_id IS NOT NULL THEN 1 END) as with_id,
        COUNT(CASE WHEN search_run_id IS NULL THEN 1 END) as without_id
    FROM gem_radar_listing_observations
    """)

    result = conn.execute(verify_query)
    row = result.fetchone()

    if row:
        total, with_id, without_id = row
        pct = 100.0 * with_id / total if total > 0 else 0
        print(f"Total observations:      {total:,}")
        print(f"With search_run_id:      {with_id:,} ({pct:.1f}%)")
        print(f"Without search_run_id:   {without_id:,}")

    # Check how many unique run IDs we have now
    runs_query = text("""
    SELECT COUNT(DISTINCT search_run_id) as unique_runs
    FROM gem_radar_listing_observations
    WHERE search_run_id IS NOT NULL
    """)

    result = conn.execute(runs_query)
    unique_runs = result.scalar()
    print(f"Unique search_run_ids:   {unique_runs:,}")

print("\n" + "="*80)
print("\n✅ Backfill complete!")
print("\nMarket Snapshot should now include all historical data.")
print("Refresh the dashboard to see the full time-series in Analytics.")
