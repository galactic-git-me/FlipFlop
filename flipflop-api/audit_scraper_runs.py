#!/usr/bin/env python
"""Audit how frequently the scraper is actually running."""
from sqlalchemy import create_engine, text
from datetime import datetime, timedelta

engine = create_engine("postgresql://flipper:flipper@127.0.0.1:5432/pcflipper")

print("🔍 SCRAPER EXECUTION AUDIT\n")
print("=" * 100)

with engine.connect() as conn:
    # Count distinct search_run_ids per day
    print("\n1️⃣  SEARCH RUNS PER DAY:\n")
    query = text("""
    SELECT
        DATE_TRUNC('day', observed_at) as scan_day,
        COUNT(DISTINCT search_run_id) as total_runs,
        COUNT(*) as total_observations,
        COUNT(DISTINCT listing_id) as unique_listings
    FROM gem_radar_listing_observations
    WHERE source = 'ebay'
      AND observed_at >= NOW() - INTERVAL '14 days'
    GROUP BY DATE_TRUNC('day', observed_at)
    ORDER BY scan_day DESC
    """)

    result = conn.execute(query)
    rows = result.fetchall()

    print(f"{'Day':<15} {'Runs':<8} {'Observations':<15} {'Unique Listings':<20}")
    print("-" * 60)
    for scan_day, runs, obs, listings in rows:
        print(f"{str(scan_day)[:10]:<15} {runs:<8} {obs:<15} {listings:<20}")

    # Check: When was the last scrape run for each major category?
    print("\n2️⃣  LAST SCRAPE RUN BY CATEGORY:\n")

    query = text("""
    SELECT
        COALESCE(search_query, category, 'unknown') as group_name,
        MAX(search_run_id) as last_run_id,
        MAX(observed_at) as last_run_time,
        CURRENT_TIMESTAMP - MAX(observed_at) as hours_since,
        COUNT(*) as observations_in_run
    FROM gem_radar_listing_observations
    WHERE source = 'ebay'
    GROUP BY search_query, category
    ORDER BY MAX(observed_at) DESC
    """)

    result = conn.execute(query)
    rows = result.fetchall()

    print(f"{'Category':<40} {'Last Run':<20} {'Hours Ago':<12} {'Obs Count':<10}")
    print("-" * 82)
    for group, run_id, last_time, hours_ago, obs_count in rows[:15]:
        hours_val = f"{int(hours_ago.total_seconds() / 3600)}" if hours_ago else "??"
        print(f"{str(group)[:40]:<40} {str(last_time)[:19]:<20} {hours_val:<12} {obs_count:<10}")

    # Check: Are runs happening regularly or sporadically?
    print("\n3️⃣  RUN FREQUENCY ANALYSIS:\n")

    query = text("""
    WITH run_times AS (
        SELECT DISTINCT
            search_run_id,
            COALESCE(search_query, category) as group_name,
            MAX(observed_at) as run_time
        FROM gem_radar_listing_observations
        WHERE source = 'ebay'
          AND observed_at >= NOW() - INTERVAL '14 days'
        GROUP BY search_run_id, COALESCE(search_query, category)
    ),
    time_deltas AS (
        SELECT
            group_name,
            run_time,
            LAG(run_time) OVER (PARTITION BY group_name ORDER BY run_time) as prev_run_time,
            EXTRACT(EPOCH FROM (run_time - LAG(run_time) OVER (PARTITION BY group_name ORDER BY run_time))) / 3600 as hours_since_prev
        FROM run_times
    )
    SELECT
        group_name,
        ROUND(AVG(hours_since_prev), 1) as avg_hours_between_runs,
        MIN(hours_since_prev) as min_hours,
        MAX(hours_since_prev) as max_hours,
        COUNT(*) as total_runs_counted
    FROM time_deltas
    WHERE hours_since_prev IS NOT NULL
    GROUP BY group_name
    ORDER BY avg_hours_between_runs
    """)

    result = conn.execute(query)
    rows = result.fetchall()

    print(f"{'Category':<40} {'Avg Interval (hrs)':<20} {'Min/Max':<25} {'Runs':<8}")
    print("-" * 93)
    for group, avg_hrs, min_hrs, max_hrs, runs in rows[:10]:
        interval_str = f"{avg_hrs}h" if avg_hrs else "?"
        min_max_str = f"{int(min_hrs or 0)}h / {int(max_hrs or 0)}h" if avg_hrs else "?"
        print(f"{str(group)[:40]:<40} {interval_str:<20} {min_max_str:<25} {runs:<8}")

print("\n" + "=" * 100)
print("\n⚠️  KEY METRIC: Average runs per day across all categories")
print("   Expected (hourly): ~24 runs per day")
print("   Expected (every 3h): ~8 runs per day")
print("   Current: Check stats above — if much lower, scraper may not be running regularly\n")
