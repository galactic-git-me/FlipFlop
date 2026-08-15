#!/usr/bin/env python
"""Update scan interval to 60 minutes (hourly)."""
from sqlalchemy import create_engine, text

engine = create_engine("postgresql://flipper:flipper@127.0.0.1:5432/pcflipper")

print("🔄 Updating scan interval to hourly (60 minutes)\n")

with engine.connect() as conn:
    # Check current setting
    query = text("SELECT gem_radar_scan_interval_minutes FROM app_settings WHERE name = 'default'")
    result = conn.execute(query)
    row = result.fetchone()

    if row:
        current = row[0]
        print(f"Current scan interval: {current} minutes ({current/60:.1f} hours)")

        # Update to 60 minutes (hourly)
        update = text("UPDATE app_settings SET gem_radar_scan_interval_minutes = 60 WHERE name = 'default'")
        conn.execute(update)
        conn.commit()
        print(f"✓ Updated to 60 minutes (1 hour)")
        print(f"\n📊 Impact:")
        print(f"  Previous: {current/60:.1f}h intervals → ~{24/(current/60):.0f} runs/day per category")
        print(f"  New:      1.0h intervals → ~24 runs/day per category")
        print(f"\n⏱️  Effect on staleness: Price updates now captured within 1 hour instead of 2-3 hours")
    else:
        print("No default setting found. Creating it...")
        insert = text("INSERT INTO app_settings (name, gem_radar_scan_interval_minutes) VALUES ('default', 60)")
        conn.execute(insert)
        conn.commit()
        print("✓ Created with 60 minute interval")
