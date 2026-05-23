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
  echo "  http://andromeda-ts:4310"
  python3 - <<'PY'
import json
import urllib.request

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

total = int(stats.get("total_listings") or demand.get("total_listings") or 0)
gems = int(stats.get("gems_count") or demand.get("total_gems") or 0)
avg_profit = float(stats.get("avg_profit") or 0.0)
gem_rate = float(demand.get("gem_rate_pct") or 0.0)
running = bool(scan.get("running"))
done = int(scan.get("completed") or 0)
scan_total = int(scan.get("total") or 0)
live_found = int(scan.get("total_found") or 0)
live_gems = int(scan.get("total_gems") or 0)

print("")
print(f"  listings: {total}   gems: {gems}   gem-rate: {gem_rate:.1f}%   avg-profit: £{avg_profit:.0f}")
print(f"  scan: {'running' if running else 'idle'}   progress: {done}/{scan_total}   found: {live_found}   live-gems: {live_gems}")
PY
  sleep 2
done
