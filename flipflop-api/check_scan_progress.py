#!/usr/bin/env python3
import psycopg2
from datetime import datetime, timedelta

conn = psycopg2.connect('postgresql://flipper:flipper@127.0.0.1:5432/pcflipper')
cur = conn.cursor()

# Check recent observations (last 10 minutes)
cutoff = (datetime.utcnow() - timedelta(minutes=10)).isoformat()

cur.execute('SELECT COUNT(*) FROM gem_radar_listing_observations WHERE observed_at > %s;', (cutoff,))
recent_count = cur.fetchone()[0]

print(f'✅ Observations added in last 10 min: {recent_count}')

# Check if using API (has epid)
cur.execute('SELECT COUNT(*) FROM gem_radar_listing_observations WHERE observed_at > %s AND epid IS NOT NULL;', (cutoff,))
api_count = cur.fetchone()[0]

print(f'✅ With epid (using Browse API): {api_count}')

# Show sample
cur.execute('SELECT title, epid, gtin, mpn, model_number FROM gem_radar_listing_observations WHERE observed_at > %s ORDER BY observed_at DESC LIMIT 5;', (cutoff,))
print(f'\n📊 Recent listings:')
for row in cur.fetchall():
    title = row[0][:55]
    epid = row[1] or "None"
    print(f'  {title}... epid={epid}')

cur.close()
conn.close()
