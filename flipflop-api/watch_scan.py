#!/usr/bin/env python3
import psycopg2
import time

print("⏱️ Monitoring scan progress...\n")
print("Snap | Observations | With epid | % API | Queue")
print("-" * 50)

for snap in range(1, 13):  # 12 snapshots = 60 seconds
    conn = psycopg2.connect('postgresql://flipper:flipper@127.0.0.1:5432/pcflipper')
    cur = conn.cursor()

    cur.execute('SELECT COUNT(*) FROM gem_radar_listing_observations;')
    obs = cur.fetchone()[0]

    cur.execute('SELECT COUNT(*) FROM gem_radar_listing_observations WHERE epid IS NOT NULL;')
    with_epid = cur.fetchone()[0]

    cur.execute('SELECT COUNT(*) FROM submission_queue;')
    queue = cur.fetchone()[0]

    pct = round(100*with_epid/obs if obs > 0 else 0, 1)
    print(f"{snap:4} | {obs:13} | {with_epid:9} | {pct:4}% | {queue:5}")

    cur.close()
    conn.close()

    if snap < 12:
        time.sleep(5)

print("\n✅ Monitoring complete")
