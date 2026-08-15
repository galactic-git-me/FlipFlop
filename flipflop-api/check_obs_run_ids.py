from sqlalchemy import create_engine, text

engine = create_engine("postgresql://flipper:flipper@127.0.0.1:5432/pcflipper")

with engine.connect() as conn:
    query = text('''
    SELECT
        search_run_id,
        COUNT(*) as count,
        MIN(observed_at)::date as first_date,
        MAX(observed_at)::date as last_date
    FROM gem_radar_listing_observations
    WHERE observed_at >= NOW() - INTERVAL '9 days'
    GROUP BY search_run_id
    ORDER BY MAX(observed_at) DESC
    LIMIT 30
    ''')

    result = conn.execute(query)
    rows = result.fetchall()

    print(f"Search run IDs in OBSERVATIONS (last 9 days):\n")
    print(f"{'Search Run ID':<40} {'Count':<8} {'First':<12} {'Last':<12}")
    print("-" * 72)

    for run_id, count, first_date, last_date in rows:
        run_label = (run_id[:37] + "...") if len(run_id) > 40 else run_id
        print(f"{run_label:<40} {count:<8} {first_date} {last_date}")

print("\n" + "="*72)

with engine.connect() as conn:
    query2 = text('''
    SELECT
        search_run_id,
        COUNT(*) as count,
        MIN(scored_at)::date as first_date,
        MAX(scored_at)::date as last_date
    FROM gem_radar_scored_listings
    WHERE scored_at >= NOW() - INTERVAL '9 days'
    GROUP BY search_run_id
    ORDER BY MAX(scored_at) DESC
    LIMIT 30
    ''')

    result = conn.execute(query2)
    rows = result.fetchall()

    print(f"\nSearch run IDs in SCORED_LISTINGS (last 9 days):\n")
    print(f"{'Search Run ID':<40} {'Count':<8} {'First':<12} {'Last':<12}")
    print("-" * 72)

    for run_id, count, first_date, last_date in rows:
        run_label = (run_id[:37] + "...") if len(run_id) > 40 else run_id
        print(f"{run_label:<40} {count:<8} {first_date} {last_date}")
