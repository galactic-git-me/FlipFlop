from sqlalchemy import create_engine, text

engine = create_engine("postgresql://flipper:flipper@127.0.0.1:5432/pcflipper")

print("🔍 SEARCHING FOR CORRUPTED PRICES...\n")

with engine.connect() as conn:
    # Look for CPUs with price < £20
    query = text("""
    SELECT
        listing_id,
        title,
        delivered_price,
        seller_name,
        source,
        observed_at::date,
        COUNT(*) OVER (PARTITION BY listing_id) as sightings
    FROM gem_radar_listing_observations
    WHERE (title ILIKE '%ryzen%' OR title ILIKE '%cpu%' OR title ILIKE '%processor%')
      AND delivered_price < 20
      AND source = 'ebay'
    ORDER BY delivered_price ASC
    LIMIT 20
    """)

    result = conn.execute(query)
    rows = result.fetchall()

    if rows:
        print(f"⚠️  Found {len(rows)} CPUs under £20:\n")
        print(f"{'Listing ID':<15} {'Price':<10} {'Title':<45} {'Date':<12}")
        print("-" * 82)
        for listing_id, title, price, seller, source, obs_date, sightings in rows:
            title_short = (title[:42] + "...") if len(title) > 45 else title
            print(f"{listing_id:<15} £{price:<9.2f} {title_short:<45} {obs_date}")
    else:
        print("✓ No corrupted CPU prices found")

    # Look for GPUs with price < £50
    print("\n" + "="*82)
    query2 = text("""
    SELECT
        listing_id,
        title,
        delivered_price,
        observed_at::date
    FROM gem_radar_listing_observations
    WHERE (title ILIKE '%gpu%' OR title ILIKE '%rtx%' OR title ILIKE '%gtx%')
      AND delivered_price < 50
      AND source = 'ebay'
    ORDER BY delivered_price ASC
    LIMIT 20
    """)

    result = conn.execute(query2)
    rows = result.fetchall()

    if rows:
        print(f"\n⚠️  Found {len(rows)} GPUs under £50:\n")
        print(f"{'Listing ID':<15} {'Price':<10} {'Title':<45} {'Date':<12}")
        print("-" * 82)
        for listing_id, title, price, obs_date in rows:
            title_short = (title[:42] + "...") if len(title) > 45 else title
            print(f"{listing_id:<15} £{price:<9.2f} {title_short:<45} {obs_date}")
    else:
        print("\n✓ No corrupted GPU prices found")
