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
taxonomy = get("/source-search-terms") or {}
telem = get("/search-telemetry/by-source?limit=2500") or {}
sources_health = get("/sources/health") or {}

total = int(stats.get("total_listings") or demand.get("total_listings") or 0)
gems = int(stats.get("gems_count") or demand.get("total_gems") or 0)
avg_profit = float(stats.get("avg_profit") or 0.0)
gem_rate = (float(gems) / float(total) * 100.0) if total > 0 else 0.0
running = bool(scan.get("running"))
live_found = int(scan.get("total_found") or 0)
live_gems = int(scan.get("total_gems") or 0)

def normalize_source_name(name: str) -> str:
    n = str(name or "").strip().lower()
    if n in {"ebay", "ebay uk", "ebay (worldwide)"}:
        return "eBay UK"
    if n in {"ebay uk auctions", "ebay auctions"}:
        return "eBay UK Auctions"
    if n in {"amazon", "amazon uk"}:
        return "Amazon"
    if n in {"facebook", "facebook marketplace"}:
        return "Facebook Marketplace"
    if n == "bargainhardware":
        return "BargainHardware"
    return str(name or "").strip()

def telemetry_source_candidates(scope: str, vendor: str) -> list[str]:
    aliases = {
        "eBay": ["eBay UK", "eBay UK Auctions"],
        "Amazon": ["Amazon"],
    }
    names = aliases.get(vendor, [normalize_source_name(vendor)])
    if scope == "cases":
        return [f"Cases:{n}" for n in names]
    if scope == "accessories":
        return [f"Accessories:{n}" for n in names]
    if scope == "upgrade_parts":
        return [f"UpgradeParts:{n}" for n in names]
    return names

def vendor_enabled(vendor: str) -> bool:
    aliases = {
        "eBay": ["eBay UK", "eBay UK Auctions"],
        "Amazon": ["Amazon"],
    }
    options = aliases.get(vendor, [normalize_source_name(vendor)])
    return any(normalize_source_name(o) in enabled_sources for o in options)

enabled_sources = set()
for s in (sources_health.get("items") or []):
    if bool((s or {}).get("enabled", False)):
        enabled_sources.add(normalize_source_name((s or {}).get("name")))

latest = {}
for src, rows in ((telem.get("items") or {}) or {}).items():
    src_n = str(src or "")
    for r in (rows or []):
        t = str((r or {}).get("term") or "").strip().lower()
        if t and (src_n, t) not in latest:
            latest[(src_n, t)] = True

term_items = taxonomy.get("items") or []
term_expected = 0
term_done = 0
for row in term_items:
    if not bool((row or {}).get("enabled", True)):
        continue
    scope = str((row or {}).get("scope") or "").strip()
    term = str((row or {}).get("term") or "").strip().lower()
    if not scope or not term:
        continue
    srcs = [str(x).strip() for x in ((row or {}).get("source_names") or []) if str(x).strip()]
    for vendor in srcs:
        candidates = telemetry_source_candidates(scope, vendor)
        if not vendor_enabled(vendor):
            continue
        term_expected += 1
        if any((cand, term) in latest for cand in candidates):
            term_done += 1

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
print(f"  scan: {'running' if running else 'idle'}   progress: {term_done}/{term_expected}   found: {live_found}   live-gems: {live_gems}")
print(f"  next scan: [{bar}]  T-{remain_txt}")
PY
  sleep 8
done
