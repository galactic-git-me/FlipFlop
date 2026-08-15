from sqlalchemy import create_engine, text

engine = create_engine("postgresql://flipper:flipper@127.0.0.1:5432/pcflipper")

with engine.connect() as conn:
    # Check current setting
    query = text("""
    SELECT gem_radar_consecutive_misses_before_inactive
    FROM app_settings
    WHERE name = 'default'
    """)

    result = conn.execute(query)
    row = result.fetchone()

    if row:
        current = row[0]
        print(f"Current consecutive_misses_before_inactive: {current}")
        print(f"(Listings inactive if missing from last {current} runs of their category)")
    else:
        print("No setting found - using default of 2")
        current = 2

    # Increase from 2 to 5 to keep listings active longer
    new_value = 5
    print(f"\nIncreasing to {new_value} to keep listings active longer...")

    update_query = text("""
    UPDATE app_settings
    SET gem_radar_consecutive_misses_before_inactive = :new_val
    WHERE name = 'default'
    """)

    result = conn.execute(update_query, {"new_val": new_value})
    conn.commit()

    print(f"✓ Updated: {result.rowcount} row(s) affected")
    print(f"\nListings will now stay active if they appear in any of the last {new_value} scans")
    print("Market Snapshot should expand significantly!")
