from sqlalchemy import create_engine, text

engine = create_engine('postgresql://flipper:flipper@127.0.0.1:5432/pcflipper')

with engine.connect() as conn:
    query = text('''
    SELECT
        search_run_id,
        COUNT(*) as count,
        MIN(scored_at)::date as first_date,
        MAX(scored_at)::date as last_date
    FROM gem_radar_scored_listings
    WHERE scored_at >= NOW() - INTERVAL '9 days'
    GROUP BY search_run_id
    ORDER BY MAX(scored_at) DESC
    ''')

    result = conn.execute(query)
    rows = result.fetchall()

    print(f"Unique search_run_ids in last 9 days: {len(rows)}\n")
    print(f"{'Search Run ID':<30} {'Count':<8} {'First':<12} {'Last':<12}")
    print("-" * 62)

    for run_id, count, first_date, last_date in rows:
        run_label = (run_id[:27] + "...") if run_id and len(run_id) > 30 else run_id
        print(f"{run_label:<30} {count:<8} {first_date} {last_date}")
