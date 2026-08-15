#!/usr/bin/env python
"""Deep dive into a specific listing to understand price update mechanism."""
from sqlalchemy import create_engine, text

engine = create_engine("postgresql://flipper:flipper@127.0.0.1:5432/pcflipper")

listing_id = "206407473762"  # MSI AM1I motherboard

print(f"🔍 DEEP DIVE: Listing {listing_id}\n")
print("=" * 120)

with engine.connect() as conn:
    # Get basic info
    query = text("""
    SELECT title, seller_name, source
    FROM gem_radar_listing_observations
    WHERE listing_id = :lid
    LIMIT 1
    """)
    result = conn.execute(query, {"lid": listing_id})
    row = result.fetchone()
    if row:
        title, seller, source = row
        print(f"\nTitle:  {title}")
        print(f"Seller: {seller}")
        print(f"Source: {source}\n")

    # Get ALL observations for this listing with full details
    query = text("""
    SELECT
        observed_at,
        delivered_price,
        item_price,
        postage_price,
        search_run_id,
        search_query,
        category,
        condition_normalised
    FROM gem_radar_listing_observations
    WHERE listing_id = :lid
    ORDER BY observed_at DESC
    """)

    result = conn.execute(query, {"lid": listing_id})
    rows = result.fetchall()

    print(f"COMPLETE OBSERVATION HISTORY ({len(rows)} records):\n")
    print(f"{'Timestamp':<20} {'Delivered':<12} {'Item Price':<12} {'Postage':<12} {'Category':<15} {'Condition':<20}")
    print("-" * 120)

    for obs_at, delivered, item_price, postage_price, run_id, search_q, cat, cond in rows:
        print(f"{str(obs_at)[:19]:<20} £{delivered:<11.2f} £{item_price or 0:<11.2f} £{postage_price or 0:<11.2f} {(cat or '?'):<15} {(cond or '?'):<20}")

    # Check: are there price variations and what causes them?
    print(f"\n\nPRICE VARIATION ANALYSIS:\n")

    query = text("""
    SELECT
        COUNT(DISTINCT delivered_price) as unique_prices,
        MIN(delivered_price) as lowest,
        MAX(delivered_price) as highest,
        MAX(delivered_price) - MIN(delivered_price) as swing
    FROM gem_radar_listing_observations
    WHERE listing_id = :lid
    """)

    result = conn.execute(query, {"lid": listing_id})
    row = result.fetchone()
    if row:
        uniq, lowest, highest, swing = row
        print(f"Unique prices observed: {uniq}")
        print(f"Range: £{lowest:.2f} to £{highest:.2f} (swing: £{swing:.2f})")

    # Check: when did the price change?
    print(f"\n\nPRICE CHANGE EVENTS:\n")

    query = text("""
    WITH priced_obs AS (
        SELECT
            observed_at,
            delivered_price,
            LAG(delivered_price) OVER (ORDER BY observed_at) as prev_price
        FROM gem_radar_listing_observations
        WHERE listing_id = :lid
        ORDER BY observed_at
    )
    SELECT
        observed_at,
        delivered_price,
        prev_price,
        ABS(delivered_price - COALESCE(prev_price, delivered_price)) as change_amount
    FROM priced_obs
    WHERE prev_price IS NOT NULL
      AND delivered_price != prev_price
    ORDER BY observed_at
    """)

    result = conn.execute(query, {"lid": listing_id})
    rows = result.fetchall()

    if rows:
        print(f"{'Time':<20} {'New Price':<12} {'Previous':<12} {'Change':<12}")
        print("-" * 55)
        for obs_at, new_price, prev_price, change in rows:
            direction = "↑" if new_price > prev_price else "↓"
            print(f"{str(obs_at)[:19]:<20} £{new_price:<11.2f} £{prev_price:<11.2f} {direction} £{change:.2f}")
    else:
        print("No price changes detected (all observations same price)")

print("\n" + "=" * 120)
print(f"\nCURRENT EBAY LISTING: £59.00")
print(f"MOST RECENT DB OBSERVATION: (see table above)")
print(f"\n⚠️  If DB shows £62.65 but eBay shows £59.00, the database is stale.")
print("    Possible causes:")
print("    1. Price observation scraping captured wrong data on 08-15")
print("    2. Price dropped AFTER 08-15 scrape, not captured yet")
print("    3. Listing was at £62.65 in morning but dropped by evening\n")
