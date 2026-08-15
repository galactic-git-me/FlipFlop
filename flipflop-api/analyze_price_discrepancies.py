#!/usr/bin/env python
"""Analyze price discrepancies between database and actual eBay listings."""
from sqlalchemy import create_engine, text

engine = create_engine("postgresql://flipper:flipper@127.0.0.1:5432/pcflipper")

print("🔍 ANALYZING PRICE DATA FRESHNESS AND PATTERNS\n")
print("=" * 100)

with engine.connect() as conn:
    # Check: How many observations per listing on average?
    print("\n1️⃣  OBSERVATION FREQUENCY:\n")

    query = text("""
    SELECT
        COUNT(DISTINCT listing_id) as total_listings,
        ROUND(AVG(obs_count), 1) as avg_observations_per_listing,
        MAX(obs_count) as max_observations,
        MIN(obs_count) as min_observations
    FROM (
        SELECT listing_id, COUNT(*) as obs_count
        FROM gem_radar_listing_observations
        WHERE source = 'ebay'
          AND observed_at >= NOW() - INTERVAL '7 days'
        GROUP BY listing_id
    ) subq
    """)

    result = conn.execute(query)
    row = result.fetchone()
    if row:
        total, avg, max_obs, min_obs = row
        print(f"Total unique listings (7d): {total}")
        print(f"Avg observations per listing: {avg}")
        print(f"Max observations: {max_obs}, Min: {min_obs}")

    # Check: What % of listings have stale prices (same price for 3+ days)?
    print("\n2️⃣  STALE PRICE DETECTION:\n")

    query = text("""
    WITH price_changes AS (
        SELECT
            listing_id,
            delivered_price,
            observed_at::date as obs_date,
            COUNT(*) OVER (
                PARTITION BY listing_id, delivered_price
                ORDER BY observed_at::date
            ) as consecutive_same_price_days
        FROM gem_radar_listing_observations
        WHERE source = 'ebay'
          AND observed_at >= NOW() - INTERVAL '7 days'
    )
    SELECT
        COUNT(DISTINCT listing_id) as listings_with_stale_prices,
        COUNT(*) as observation_records_stale,
        ROUND(100.0 * COUNT(DISTINCT listing_id) / (
            SELECT COUNT(DISTINCT listing_id)
            FROM gem_radar_listing_observations
            WHERE source = 'ebay'
              AND observed_at >= NOW() - INTERVAL '7 days'
        ), 1) as pct_listings_affected
    FROM price_changes
    WHERE consecutive_same_price_days >= 3
    """)

    result = conn.execute(query)
    row = result.fetchone()
    if row:
        listings, records, pct = row
        print(f"Listings with stale prices (3+ days same): {listings}")
        print(f"Total observation records affected: {records}")
        print(f"Percentage of listings affected: {pct}%")

    # Check: How many listings show price changes in last 7 days?
    print("\n3️⃣  PRICE MOVEMENT:\n")

    query = text("""
    WITH price_stats AS (
        SELECT
            listing_id,
            MIN(delivered_price) as min_price,
            MAX(delivered_price) as max_price,
            COUNT(DISTINCT delivered_price) as unique_prices
        FROM gem_radar_listing_observations
        WHERE source = 'ebay'
          AND observed_at >= NOW() - INTERVAL '7 days'
        GROUP BY listing_id
    )
    SELECT
        COUNT(*) as total_analyzed,
        COUNT(CASE WHEN min_price = max_price THEN 1 END) as no_price_change,
        COUNT(CASE WHEN min_price < max_price THEN 1 END) as price_increased,
        COUNT(CASE WHEN min_price > max_price THEN 1 END) as price_decreased,
        ROUND(CAST(AVG(ABS(max_price - min_price)) AS numeric), 2) as avg_price_swing
    FROM price_stats
    """)

    result = conn.execute(query)
    row = result.fetchone()
    if row:
        total, no_change, increased, decreased, avg_swing = row
        print(f"Total listings analyzed: {total}")
        print(f"No price change: {no_change}")
        print(f"Price increased during period: {increased}")
        print(f"Price decreased during period: {decreased}")
        print(f"Average price swing: £{avg_swing}")

    # Check: Most recent observations - how old are they?
    print("\n4️⃣  DATA FRESHNESS:\n")

    query = text("""
    SELECT
        DATE_TRUNC('day', MAX(observed_at)) as last_observation,
        CURRENT_TIMESTAMP - MAX(observed_at) as hours_since_last_obs,
        COUNT(DISTINCT listing_id) as listings_with_recent_obs
    FROM gem_radar_listing_observations
    WHERE source = 'ebay'
    """)

    result = conn.execute(query)
    row = result.fetchone()
    if row:
        last_obs, hours_ago, count = row
        print(f"Last observation: {last_obs}")
        print(f"Hours since last obs: {hours_ago}")
        print(f"Listings with recent observations: {count}")

print("\n" + "=" * 100)
print("\nKEY QUESTION: Why aren't price CHANGES being captured consistently?")
print("Hypothesis: Scraper may be deduping/skipping listings that haven't changed")
print("           or observations may not be touching/updating when prices change.")
