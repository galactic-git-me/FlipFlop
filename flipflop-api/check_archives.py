import psycopg2
import time

time.sleep(3)  # Wait for connections to close
conn = psycopg2.connect('postgresql://flipper:flipper@127.0.0.1:5432/pcflipper')
cur = conn.cursor()

cur.execute("""
SELECT tablename
FROM pg_tables
WHERE schemaname='public' AND tablename LIKE '%archive%'
ORDER BY tablename;
""")

print('Archive tables created before failure:')
archives = cur.fetchall()
if archives:
    for row in archives:
        cur.execute(f"SELECT COUNT(*) FROM {row[0]}")
        count = cur.fetchone()[0]
        print(f'  ✓ {row[0]:50} ({count:,} rows)')
else:
    print('  (none)')

cur.close()
conn.close()
