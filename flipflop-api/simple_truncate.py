#!/usr/bin/env python3
import psycopg2

conn = psycopg2.connect('postgresql://flipper:flipper@127.0.0.1:5432/pcflipper', connect_timeout=5)
conn.set_session(autocommit=True)
cur = conn.cursor()

tables = [
    'gem_radar_scored_listings',
    'gem_radar_listing_observations',
    'gem_radar_sold_observations',
    'gem_radar_amazon_observations',
]

for table in tables:
    cur.execute(f"TRUNCATE {table} CASCADE;")
    print(f"✓ {table}")

conn.close()
print("\n✅ Done!")
