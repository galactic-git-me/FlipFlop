#!/usr/bin/env bash
set +e
while true; do
  clear
  cat <<ASCII

  ███████╗██╗     ██╗██████╗ ███████╗██╗      ██████╗ ██████╗
  ██╔════╝██║     ██║██╔══██╗██╔════╝██║     ██╔═══██╗██╔══██╗
  █████╗  ██║     ██║██████╔╝█████╗  ██║     ██║   ██║██████╔╝
  ██╔══╝  ██║     ██║██╔═══╝ ██╔══╝  ██║     ██║   ██║██╔═══╝
  ██║     ███████╗██║██║     ██║     ███████╗╚██████╔╝██║
  ╚═╝     ╚══════╝╚═╝╚═╝     ╚═╝     ╚══════╝ ╚═════╝ ╚═╝

ASCII
  python3 - <<'PY'
import json
import urllib.request
from datetime import datetime, timezone

base = "http://andromeda-ts:4311/api"

def get(path):
    try:
        with urllib.request.urlopen(base + path, timeout=3) as r:
            return json.load(r)
    except Exception:
        return {}

stats = get("/listings/stats") or {}
demand = get("/demand/summary") or {}
scan = get("/swarms/scan/status") or {}
schedule = get("/schedule") or []

total = int(stats.get("total_listings") or demand.get("total_listings") or 0)
gems = int(stats.get("gems_count") or demand.get("total_gems") or 0)
avg_profit = float(stats.get("avg_profit") or 0.0)
gem_rate = (float(gems) / float(total) * 100.0) if total > 0 else 0.0
running = bool(scan.get("running"))
done = int(scan.get("completed") or 0)
scan_total = int(scan.get("total") or 0)
live_found = int(scan.get("total_found") or 0)
live_gems = int(scan.get("total_gems") or 0)

def parse_iso(ts):
    if not ts:
        return None
    try:
        dt = datetime.fromisoformat(str(ts).replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    except Exception:
        return None

flip = next((j for j in schedule if str((j or {}).get("id")) == "flip_opportunities"), {})
last_dt = parse_iso((flip or {}).get("last_run_at"))
next_dt = parse_iso((flip or {}).get("next_run_at"))
now = datetime.now(timezone.utc)
bar = "—"
remain_txt = "—"
if last_dt and next_dt and next_dt > last_dt:
    total = max(1, int((next_dt - last_dt).total_seconds()))
    elapsed = int((now - last_dt).total_seconds())
    elapsed = max(0, min(elapsed, total))
    remain = max(0, int((next_dt - now).total_seconds()))
    pct = elapsed / float(total)
    width = 28
    filled = int(round(width * pct))
    bar = "█" * filled + "░" * (width - filled)
    rm, rs = divmod(remain, 60)
    rh, rm = divmod(rm, 60)
    remain_txt = f"{rh:02d}:{rm:02d}:{rs:02d}"

print("")
print(f"  listings: {total}   gems: {gems}   gem-rate: {gem_rate:.1f}%   avg-profit: £{avg_profit:.0f}")
print(f"  scan: {'running' if running else 'idle'}   progress: {done}/{scan_total}   found: {live_found}   live-gems: {live_gems}")
print(f"  next scan: [{bar}]  T-{remain_txt}")
PY
  sleep 8
done
