#!/usr/bin/env python
from sqlalchemy import create_engine, text
from datetime import datetime, timedelta

engine = create_engine("postgresql://flipper:flipper@127.0.0.1:5432/pcflipper")

print("📊 Data Flow Analysis\n")
print("="*90)

# Check listing observations by date
date_query = text("""
SELECT
    DATE(observed_at) as observation_date,
    COUNT(*) as total_listings,
    COUNT(DISTINCT listing_id) as unique_listings,
    COUNT(DISTINCT source) as sources,
    MIN(delivered_price) as min_price,
    MAX(delivered_price) as max_price,
    ROUND(AVG(delivered_price)::numeric, 2) as avg_price
FROM gem_radar_listing_observations
WHERE observed_at >= NOW() - INTERVAL '30 days'
GROUP BY DATE(observed_at)
ORDER BY observation_date DESC
LIMIT 30
""")

print("\n📅 LISTINGS BY DATE (Last 30 days):\n")
with engine.connect() as conn:
    result = conn.execute(date_query)
    rows = result.fetchall()

    if rows:
        print(f"{'Date':<15} {'Total':<10} {'Unique':<10} {'Sources':<10} {'Price Range':<25} {'Avg Price':<12}")
        print("-" * 90)
        for date, total, unique, sources, min_p, max_p, avg_p in rows:
            price_range = f"£{min_p:.0f}-£{max_p:.0f}"
            print(f"{str(date):<15} {total:<10} {unique:<10} {sources:<10} {price_range:<25} £{avg_p:<11}")
    else:
        print("No recent data found")

# Check scan runs
print("\n" + "="*90)
print("\n🔄 SCAN RUN HISTORY (Recent):\n")

scan_query = text("""
SELECT
    search_run_id,
    MIN(scored_at) as first_scored,
    MAX(scored_at) as last_scored,
    COUNT(*) as listings_scored,
    COUNT(CASE WHEN classification = 'GEM' THEN 1 END) as gem_count,
    COUNT(CASE WHEN classification = 'SUPER_GEM' THEN 1 END) as super_gem_count,
    COUNT(DISTINCT source) as sources
FROM gem_radar_scored_listings
WHERE search_run_id IS NOT NULL
  AND scored_at >= NOW() - INTERVAL '7 days'
GROUP BY search_run_id
ORDER BY MIN(scored_at) DESC
LIMIT 20
""")

with engine.connect() as conn:
    result = conn.execute(scan_query)
    rows = result.fetchall()

    if rows:
        print(f"{'Scan Run ID':<30} {'Time':<20} {'Listings':<12} {'Gems':<8} {'Super':<8} {'Sources':<10}")
        print("-" * 90)
        for run_id, first_scored, last_scored, listings, gems, super_gems, sources in rows:
            run_label = (run_id[:25] + "...") if run_id and len(run_id) > 25 else run_id
            time_label = f"{first_scored.strftime('%m/%d %H:%M')}" if first_scored else "N/A"
            print(f"{run_label:<30} {time_label:<20} {listings:<12} {gems:<8} {super_gems:<8} {sources:<10}")
    else:
        print("No recent scan runs found")

# Overall stats
print("\n" + "="*90)
print("\n📈 OVERALL DATABASE STATS:\n")

stats_query = text("""
SELECT
    COUNT(*) as total_observations,
    COUNT(DISTINCT listing_id) as unique_listings,
    COUNT(DISTINCT DATE(observed_at)) as days_of_data,
    MIN(observed_at) as earliest_observation,
    MAX(observed_at) as latest_observation,
    COUNT(DISTINCT source) as unique_sources,
    COUNT(CASE WHEN classification = 'GEM' THEN 1 END) as total_gems,
    COUNT(CASE WHEN classification = 'SUPER_GEM' THEN 1 END) as total_super_gems
FROM gem_radar_scored_listings
WHERE source != 'temu'
""")

with engine.connect() as conn:
    result = conn.execute(stats_query)
    row = result.fetchone()

    if row:
        total_obs, unique_list, days, earliest, latest, sources, gems, super_gems = row
        print(f"Total Observations:    {total_obs:,}")
        print(f"Unique Listings:       {unique_list:,}")
        print(f"Days of Data:          {days}")
        print(f"Date Range:            {earliest.date()} to {latest.date()}")
        print(f"Unique Sources:        {sources}")
        print(f"Total GEMs:            {gems:,}")
        print(f"Total SUPER GEMs:      {super_gems:,}")

        if days and days > 0:
            print(f"\n✅ Data flowing smoothly — {days} days of active scanning")
        else:
            print(f"\n⚠️  Limited data history")

print("\n" + "="*90)
