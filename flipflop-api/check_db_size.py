#!/usr/bin/env python3
import psycopg2

conn = psycopg2.connect("postgresql://flipper:flipper@127.0.0.1:5432/pcflipper")
cur = conn.cursor()

# Database size
cur.execute("SELECT pg_size_pretty(pg_database_size('pcflipper')) as db_size;")
result = cur.fetchone()
print(f"Total database size: {result[0]}\n")

# Gem radar table sizes
cur.execute("""
SELECT tablename, pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) as size
FROM pg_tables
WHERE tablename LIKE 'gem_radar%'
ORDER BY pg_total_relation_size(schemaname||'.'||tablename) DESC;
""")
print("Gem Radar table sizes:")
for row in cur.fetchall():
    print(f"  {row[0]:45} {row[1]:>15}")

cur.close()
conn.close()
