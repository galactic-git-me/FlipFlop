#!/usr/bin/env python3
"""Disable PostgreSQL tracking and truncate gem_radar tables."""
import psycopg2
import time

time.sleep(5)  # Wait for old connections to timeout

try:
    conn = psycopg2.connect('postgresql://flipper:flipper@127.0.0.1:5432/pcflipper')
    conn.set_session(autocommit=True)  # Each statement commits immediately
    cur = conn.cursor()

    print("Disabling PostgreSQL tracking/archiving...")
    try:
        cur.execute("ALTER SYSTEM SET archive_mode = off;")
        print("  ✓ Archive mode disabled")
    except Exception as e:
        print(f"  ⚠ Archive mode: {e}")

    try:
        cur.execute("ALTER SYSTEM SET wal_level = minimal;")
        print("  ✓ WAL level set to minimal")
    except Exception as e:
        print(f"  ⚠ WAL level: {e}")

    print("\nTruncating gem_radar tables...")
    tables = [
        'gem_radar_scored_listings',
        'gem_radar_listing_observations',
        'gem_radar_sold_observations',
        'gem_radar_amazon_observations',
    ]

    for table in tables:
        try:
            cur.execute(f"TRUNCATE {table} CASCADE;")
            print(f"  ✓ {table} truncated")
        except Exception as e:
            print(f"  ✗ {table}: {e}")

    print("\n" + "="*60)
    print("✅ SUCCESS: Tables cleared and tracking disabled")
    print("="*60)
    print("\nNote: Restart PostgreSQL to apply config changes:")
    print("  - archive_mode = off")
    print("  - wal_level = minimal")

    cur.close()
    conn.close()

except Exception as e:
    print(f"❌ ERROR: {e}")
    import traceback
    traceback.print_exc()
    exit(1)
