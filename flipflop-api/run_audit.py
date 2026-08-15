#!/usr/bin/env python
from sqlalchemy import create_engine, text

# Connect directly to PostgreSQL
engine = create_engine("postgresql://localhost/gem_radar")

query = text("""
SELECT
    listing_id,
    title,
    delivered_price,
    actual_listing_price,
    CASE
        WHEN delivered_price < 20 AND title ILIKE '%cpu%' THEN 'SUSPICIOUSLY_LOW_CPU'
        WHEN delivered_price < 20 AND title ILIKE '%gpu%' THEN 'SUSPICIOUSLY_LOW_GPU'
        WHEN delivered_price < 20 AND title ILIKE '%motherboard%' THEN 'SUSPICIOUSLY_LOW_MOBO'
        WHEN delivered_price < 20 AND title ILIKE '%ram%' THEN 'SUSPICIOUSLY_LOW_RAM'
        WHEN delivered_price < 20 AND title ILIKE '%ssd%' THEN 'SUSPICIOUSLY_LOW_SSD'
        WHEN delivered_price < 20 AND title ILIKE '%psu%' THEN 'SUSPICIOUSLY_LOW_PSU'
        ELSE 'NORMAL'
    END as flag
FROM gem_radar_ebay_observation
WHERE delivered_price < 20 AND (
    title ILIKE '%cpu%' OR title ILIKE '%gpu%' OR
    title ILIKE '%motherboard%' OR title ILIKE '%ram%' OR title ILIKE '%ssd%' OR
    title ILIKE '%psu%'
)
LIMIT 50
""")

with engine.connect() as conn:
    result = conn.execute(query)
    rows = result.fetchall()

    print(f"Found {len(rows)} suspicious listings with prices under £20:\n")
    print(f"{'ID':<20} {'Price':<12} {'Flag':<20} {'Title':<50}")
    print("-" * 102)

    for row in rows:
        listing_id, title, delivered, actual, flag = row
        title_short = (title[:45] + "...") if title and len(title) > 50 else title
        print(f"{listing_id:<20} £{delivered:<11.2f} {flag:<20} {title_short}")

print("\n\nNow checking ALL listings for prices that seem wrong (any price < £50 for core components):")
print("-" * 102)

query2 = text("""
SELECT
    listing_id,
    title,
    delivered_price,
    COUNT(*) as total_in_category
FROM gem_radar_ebay_observation
WHERE (title ILIKE '%cpu%' OR title ILIKE '%gpu%' OR title ILIKE '%motherboard%')
  AND delivered_price IS NOT NULL
GROUP BY listing_id, title, delivered_price
HAVING delivered_price < 50
ORDER BY delivered_price ASC
LIMIT 30
""")

with engine.connect() as conn:
    result = conn.execute(query2)
    rows = result.fetchall()

    print(f"{'ID':<20} {'Price':<12} {'Title':<50}")
    print("-" * 82)
    for row in rows:
        listing_id, title, delivered, _ = row
        title_short = (title[:47] + "...") if title and len(title) > 50 else title
        print(f"{listing_id:<20} £{delivered:<11.2f} {title_short}")
