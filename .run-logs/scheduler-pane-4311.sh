#!/usr/bin/env bash
set +e
while true; do
  clear
  echo "Scheduler"
  echo "API: http://andromeda-ts:4311/api/schedule"
  echo
  python3 - <<'PY'
import json
import urllib.request
from datetime import datetime, timezone

def age(ts):
    if not ts:
        return "—"
    try:
        dt = datetime.fromisoformat(ts.replace("Z","+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        secs = int((datetime.now(timezone.utc)-dt.astimezone(timezone.utc)).total_seconds())
        if secs < 0:
            return "due"
        m, s = divmod(secs, 60)
        h, m = divmod(m, 60)
        return f"{h}h{m:02d}m" if h else f"{m:02d}m{s:02d}s"
    except Exception:
        return "—"

url = "http://andromeda-ts:4311/api/schedule"
try:
    with urllib.request.urlopen(url, timeout=4) as r:
        rows = json.load(r)
except Exception as e:
    print(f"schedule unavailable: {e}")
    rows = []

print(f"{'JOB':30} {'EN':3} {'NEXT':10} {'LAST':10} STATUS")
print("-"*80)
for j in rows:
    jid = str(j.get("id",""))[:30]
    en = "yes" if j.get("enabled") else "no"
    nxt = age(j.get("next_run_at"))
    last = age(j.get("last_run_at"))
    st = str(j.get("last_status") or "—")
    print(f"{jid:30} {en:3} {nxt:10} {last:10} {st}")
PY
  sleep 2
done
