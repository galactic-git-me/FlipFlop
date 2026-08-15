#!/usr/bin/env python
from sqlalchemy import create_engine, text

engine = create_engine("postgresql://flipper:flipper@127.0.0.1:5432/pcflipper")

print("🧹 Removing all Temu listings and pricing data...\n")

queries = [
    ("gem_radar_listing_observations", """
        DELETE FROM gem_radar_listing_observations WHERE source = 'temu'
    """),
    ("gem_radar_scored_listings", """
        DELETE FROM gem_radar_scored_listings WHERE source = 'temu'
    """),
    ("gem_radar_sold_observations", """
        DELETE FROM gem_radar_sold_observations
        WHERE listing_id IN (
            SELECT listing_id FROM gem_radar_listing_observations
            WHERE source = 'temu'
        )
    """),
    ("gem_radar_cpk_listing_price", """
        DELETE FROM gem_radar_cpk_listing_price
        WHERE listing_id IN (
            SELECT listing_id FROM gem_radar_listing_observations
            WHERE source = 'temu'
        )
    """),
    ("gem_radar_cpk_market_price", """
        DELETE FROM gem_radar_cpk_market_price
        WHERE listing_id IN (
            SELECT listing_id FROM gem_radar_listing_observations
            WHERE source = 'temu'
        )
    """),
]

with engine.connect() as conn:
    for table_name, query in queries:
        try:
            result = conn.execute(text(query))
            deleted = result.rowcount
            conn.commit()
            print(f"✓ {table_name}: Deleted {deleted} rows")
        except Exception as e:
            print(f"⚠ {table_name}: {str(e)}")
            conn.rollback()

print("\n" + "="*60)
print("Verifying cleanup...")
print("="*60 + "\n")

verify_queries = [
    ("gem_radar_listing_observations", "SELECT COUNT(*) FROM gem_radar_listing_observations WHERE source = 'temu'"),
    ("gem_radar_scored_listings", "SELECT COUNT(*) FROM gem_radar_scored_listings WHERE source = 'temu'"),
]

with engine.connect() as conn:
    for table_name, query in verify_queries:
        result = conn.execute(text(query))
        count = result.scalar()
        status = "✓" if count == 0 else "⚠"
        print(f"{status} {table_name}: {count} remaining Temu records")

print("\nSummary statistics after cleanup:")
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

print("\n✅ Cleanup complete! Market prices should now be accurate.")
