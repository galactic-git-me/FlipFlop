#!/usr/bin/env python
from sqlalchemy import create_engine, text

# Connect directly to PostgreSQL
engine = create_engine("postgresql://flipper:flipper@127.0.0.1:5432/pcflipper")

# Query gem_radar_listing_observations for suspicious low prices
query = text("""
SELECT
    listing_id,
    title,
    delivered_price,
    source
FROM gem_radar_listing_observations
WHERE delivered_price < 20 AND (
    title ILIKE '%cpu%' OR title ILIKE '%gpu%' OR
    title ILIKE '%motherboard%' OR title ILIKE '%ram%' OR title ILIKE '%ssd%' OR
    title ILIKE '%psu%'
)
ORDER BY delivered_price ASC
LIMIT 50
""")

with engine.connect() as conn:
    result = conn.execute(query)
    rows = result.fetchall()

    if rows:
        print(f"🚨 CRITICAL: Found {len(rows)} suspicious listings with prices under £20:\n")
        print(f"{'ID':<20} {'Price':<12} {'Source':<12} {'Title':<40}")
        print("-" * 84)

        for row in rows:
            listing_id, title, delivered, source = row
            title_short = (title[:37] + "...") if title and len(title) > 40 else title
            print(f"{listing_id:<20} £{delivered:<11.2f} {str(source):<12} {title_short}")
    else:
        print("✓ No listings with prices under £20 found.")

print("\n\nChecking for ANY suspicious prices under £50 for core components:")
print("-" * 84)

query2 = text("""
SELECT
    listing_id,
    title,
    delivered_price,
    source
FROM gem_radar_listing_observations
WHERE (title ILIKE '%cpu%' OR title ILIKE '%gpu%' OR title ILIKE '%motherboard%' OR title ILIKE '%ram%')
  AND delivered_price IS NOT NULL
  AND delivered_price < 50
ORDER BY delivered_price ASC
LIMIT 50
""")

with engine.connect() as conn:
    result = conn.execute(query2)
    rows = result.fetchall()

    if rows:
        print(f"Found {len(rows)} listings with questionable prices under £50:\n")
        print(f"{'ID':<20} {'Price':<12} {'Source':<12} {'Title':<40}")
        print("-" * 84)
        for row in rows:
            listing_id, title, delivered, source = row
            title_short = (title[:37] + "...") if title and len(title) > 40 else title
            print(f"{listing_id:<20} £{delivered:<11.2f} {str(source):<12} {title_short}")
    else:
        print("✓ No listings under £50 found.")

print("\n\nSummary statistics:")
summary = text("""
SELECT
    COUNT(*) as total_records,
    COUNT(DISTINCT listing_id) as unique_listings,
    MIN(delivered_price) as min_price,
    MAX(delivered_price) as max_price,
    AVG(delivered_price)::numeric(10,2) as avg_price
FROM gem_radar_listing_observations
WHERE delivered_price IS NOT NULL
""")

with engine.connect() as conn:
    result = conn.execute(summary)
    row = result.fetchone()
    if row:
        total, unique, min_p, max_p, avg_p = row
        print(f"Total observations: {total:,}")
        print(f"Unique listings: {unique:,}")
        print(f"Price range: £{min_p:.2f} - £{max_p:.2f}")
        print(f"Average price: £{avg_p}")
