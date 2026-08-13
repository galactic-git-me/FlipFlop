#!/usr/bin/env python3
"""Backup gem_radar tables to archive and clear live data."""
import os
from sqlalchemy import create_engine, text
from dotenv import load_dotenv

load_dotenv()

# Get DB connection string (use sync version, not asyncpg)
db_url = os.getenv("SYNC_DATABASE_URL")
if not db_url:
    # Use default sync URL from config
    db_url = "postgresql://flipper:flipper@127.0.0.1:5432/pcflipper"
    print(f"Using default database URL: {db_url.split('@')[1]}")

engine = create_engine(db_url)

sql_statements = [
    # Create archive tables
    "CREATE TABLE gem_radar_scored_listings_archive_20260801 AS SELECT * FROM gem_radar_scored_listings",
    "CREATE TABLE gem_radar_listing_observations_archive_20260801 AS SELECT * FROM gem_radar_listing_observations",
    "CREATE TABLE gem_radar_sold_observations_archive_20260801 AS SELECT * FROM gem_radar_sold_observations",
    "CREATE TABLE gem_radar_amazon_observations_archive_20260801 AS SELECT * FROM gem_radar_amazon_observations",
    "CREATE TABLE gem_radar_seller_profile_archive_20260801 AS SELECT * FROM gem_radar_seller_profile",

    # Clear live tables
    "TRUNCATE gem_radar_scored_listings CASCADE",
    "TRUNCATE gem_radar_listing_observations CASCADE",
    "TRUNCATE gem_radar_sold_observations CASCADE",
    "TRUNCATE gem_radar_amazon_observations CASCADE",
    "TRUNCATE gem_radar_seller_profile CASCADE",

    # Verify archive counts
    "SELECT COUNT(*) as scored_count FROM gem_radar_scored_listings_archive_20260801",
    "SELECT COUNT(*) as obs_count FROM gem_radar_listing_observations_archive_20260801",
    "SELECT COUNT(*) as sold_count FROM gem_radar_sold_observations_archive_20260801",
]

try:
    # Each statement in its own connection/transaction
    for statement in sql_statements:
        print(f"\n→ {statement[:60]}...")
        try:
            with engine.connect() as conn:
                result = conn.execute(text(statement))
                if 'SELECT' in statement.upper() and result.returns_rows:
                    for row in result:
                        print(f"  ✓ Count: {row[0]}")
                else:
                    print(f"  ✓ Executed")
                conn.commit()
        except Exception as e:
            if "does not exist" in str(e):
                print(f"  ⊘ Table doesn't exist (skipped)")
            else:
                raise

    print("\n" + "="*60)
    print("✅ SUCCESS: Backup created and live tables cleared")
    print("="*60)
    print("\nArchive tables created:")
    print("  - gem_radar_scored_listings_archive_20260801")
    print("  - gem_radar_listing_observations_archive_20260801")
    print("  - gem_radar_sold_observations_archive_20260801")
    print("  - gem_radar_amazon_observations_archive_20260801")
    print("  - gem_radar_seller_profile_archive_20260801")
    print("\nLive tables cleared and ready for fresh data.")

except Exception as e:
    print(f"\n❌ ERROR: {e}")
    import traceback
    traceback.print_exc()
    exit(1)
