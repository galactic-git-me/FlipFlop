from sqlalchemy import create_engine, text

 

with engine.connect() as conn:
    query = text('''
    SELECT
        COUNT(*) as total_scored,
        COUNT(CASE WHEN search_run_id IS NOT NULL THEN 1 END) as with_run_id,
        COUNT(CASE WHEN search_run_id IS NULL THEN 1 END) as without_run_id,
        ROUND(100.0 * COUNT(CASE WHEN search_run_id IS NOT NULL THEN 1 END) / COUNT(*), 1) as pct_with_id
    FROM gem_radar_scored_listings
    WHERE scored_at >= NOW() - INTERVAL '9 days'
    ''')

    result = conn.execute(query)
    row = result.fetchone()

    if row:
        total, with_id, without_id, pct = row
        print(f'Total scored (9 days):  {total:,}')
        print(f'With search_run_id:     {with_id:,} ({pct}%)')
        print(f'Without search_run_id:  {without_id:,}')
        print()
        if pct < 50:
            print('🔴 PROBLEM: Most scored listings missing search_run_id')
            print('   Analytics graph filters: WHERE search_run_id IS NOT NULL')
            print('   Result: Only today shows up (cpk-phase2-classify is the only recent one with an ID)')
        else:
            print('✓ search_run_id coverage looks good')
