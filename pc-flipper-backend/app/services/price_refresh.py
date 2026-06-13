"""
Daily component price refresh — keeps ALL estimator prices current.

Fetches live eBay UK *sold* prices for:
  - Budget upgrade components (what we spend: GPU, RAM, SSD, PSU, case)
  - GPU standalone resale values (what a GPU adds to a complete PC)
  - CPU/system baseline values (what a bare system with that CPU sells for)

Writes to data/price_benchmarks.json. estimator.py reads this file at
runtime so profit calculations always use today's actual market prices.

Fallback: if the file is missing or older than 48 h, estimator.py falls
back to its hardcoded defaults (which are themselves updated to June 2026
values and are a reasonable safety net).
"""
from __future__ import annotations

import asyncio
import json
import re
import time
from datetime import datetime
from pathlib import Path
from statistics import median

import httpx
from bs4 import BeautifulSoup
from fake_useragent import UserAgent
import structlog

log = structlog.get_logger(__name__)

_BENCHMARKS_FILE = Path(__file__).resolve().parents[2] / "data" / "price_benchmarks.json"
_ua = UserAgent()

# ─────────────────────────────────────────────────────────────────────────────
# Query definitions
# Each entry: (key, ebay_query, price_floor, price_ceiling)
#
# GPU queries price the STANDALONE card — we derive the "add to system resale"
# value as 90% of standalone (buyers pay slightly less inside a system because
# they can't resell the GPU independently).
#
# CPU_SYSTEM queries are for a BARE GAMING PC with that CPU class and no GPU.
# These map directly to CPU_BASE_RESALE values.
# ─────────────────────────────────────────────────────────────────────────────

BUDGET_COMPONENT_QUERIES: list[tuple[str, str, float, float]] = [
    # RAM
    ("cost_ram_32gb_ddr4",      "32gb ddr4 desktop ram kit 3200",          30.0,  400.0),
    ("cost_ram_64gb_ddr4",      "64gb ddr4 desktop ram kit 3200",          60.0,  600.0),
    ("cost_ram_32gb_ddr5",      "32gb ddr5 desktop ram kit 5600",          50.0,  500.0),
    ("cost_ram_64gb_ddr5",      "64gb ddr5 desktop ram kit 5600",          80.0,  700.0),
    # GPUs (our buy cost)
    ("cost_gpu_rtx3060",        "rtx 3060 12gb graphics card",            120.0,  380.0),
    ("cost_gpu_rtx4060",        "rtx 4060 8gb graphics card",             150.0,  450.0),
    ("cost_gpu_rx6700xt",       "rx 6700 xt graphics card",               100.0,  360.0),
    # Storage
    ("cost_ssd_1tb_nvme",       "1tb nvme m.2 ssd 2280",                   25.0,  130.0),
    ("cost_ssd_2tb_nvme",       "2tb nvme m.2 ssd 2280",                   40.0,  200.0),
    # PSU
    ("cost_psu_650w",           "650w 80 plus bronze psu modular",          25.0,  120.0),
    ("cost_psu_750w",           "750w 80 plus gold psu modular",            35.0,  150.0),
    # Cases — themed RGB gaming (what we pay to upgrade)
    ("cost_case_rgb_atx",       "rgb gaming pc case atx mid tower",         25.0,  120.0),
    ("cost_case_rgb_mesh",      "mesh gaming pc case argb mid tower",       30.0,  150.0),
    ("cost_case_mini_itx",      "mini itx gaming case rgb",                 25.0,  130.0),
    # AM5 platform (mobo + DDR5 — needed before any AM5 system can be upgraded)
    ("cost_mobo_am5_b650",      "am5 b650 motherboard",                     80.0,  250.0),
    ("cost_mobo_am5_x670",      "am5 x670 motherboard",                    120.0,  380.0),
    # AM4 platform (mobo — often the upgrade needed for R5 5600 flips)
    ("cost_mobo_am4_b550",      "am4 b550 motherboard",                     40.0,  180.0),
    ("cost_mobo_am4_x570",      "am4 x570 motherboard",                     60.0,  250.0),
    # Accessories — commonly bundled or sold with flips
    ("cost_wifi_card_pcie",     "pcie wifi 6 card desktop",                 15.0,   80.0),
    ("cost_cpu_cooler_120mm",   "120mm aio liquid cooler",                   20.0,  100.0),
    ("cost_cpu_cooler_air",     "cpu air cooler tower 120mm",                10.0,   70.0),
    ("cost_keyboard_rgb",       "rgb gaming keyboard mechanical",            15.0,  100.0),
    ("cost_mouse_gaming",       "gaming mouse rgb",                          10.0,   70.0),
    ("cost_headset_gaming",     "gaming headset usb rgb",                    15.0,   80.0),
    ("cost_monitor_1080p",      "24 inch 1080p gaming monitor 144hz",        50.0,  250.0),
    ("cost_monitor_1440p",      "27 inch 1440p gaming monitor 144hz",        80.0,  400.0),
]

GPU_RESALE_QUERIES: list[tuple[str, str, float, float]] = [
    # GTX 10-series
    ("gpu_gtx1060_6gb",     "gtx 1060 6gb graphics card",            30.0,  200.0),
    ("gpu_gtx1070",         "gtx 1070 8gb graphics card",            50.0,  250.0),
    ("gpu_gtx1080",         "gtx 1080 8gb graphics card",            70.0,  300.0),
    ("gpu_gtx1080ti",       "gtx 1080 ti graphics card",            100.0,  380.0),
    # GTX 16-series
    ("gpu_gtx1660super",    "gtx 1660 super graphics card",          50.0,  250.0),
    ("gpu_gtx1660ti",       "gtx 1660 ti graphics card",             50.0,  250.0),
    # RTX 20-series
    ("gpu_rtx2060",         "rtx 2060 6gb graphics card",            80.0,  300.0),
    ("gpu_rtx2070",         "rtx 2070 8gb graphics card",           100.0,  380.0),
    ("gpu_rtx2080",         "rtx 2080 8gb graphics card",           130.0,  450.0),
    # RTX 30-series
    ("gpu_rtx3060",         "rtx 3060 12gb graphics card",          120.0,  380.0),
    ("gpu_rtx3060ti",       "rtx 3060 ti graphics card",            120.0,  400.0),
    ("gpu_rtx3070",         "rtx 3070 8gb graphics card",           150.0,  480.0),
    ("gpu_rtx3080",         "rtx 3080 10gb graphics card",          200.0,  600.0),
    ("gpu_rtx3090",         "rtx 3090 24gb graphics card",          250.0,  700.0),
    # RTX 40-series
    ("gpu_rtx4060",         "rtx 4060 8gb graphics card",           150.0,  450.0),
    ("gpu_rtx4060ti",       "rtx 4060 ti graphics card",            180.0,  500.0),
    ("gpu_rtx4070",         "rtx 4070 12gb graphics card",          220.0,  600.0),
    ("gpu_rtx4070super",    "rtx 4070 super graphics card",         250.0,  650.0),
    ("gpu_rtx4080",         "rtx 4080 16gb graphics card",          400.0, 1000.0),
    # AMD RX 5xx
    ("gpu_rx580",           "rx 580 8gb graphics card",              25.0,  150.0),
    # AMD RX 5xxx
    ("gpu_rx5700xt",        "rx 5700 xt graphics card",              80.0,  280.0),
    # AMD RX 6xxx
    ("gpu_rx6600",          "rx 6600 8gb graphics card",             80.0,  280.0),
    ("gpu_rx6600xt",        "rx 6600 xt graphics card",              80.0,  280.0),
    ("gpu_rx6700xt",        "rx 6700 xt graphics card",             100.0,  360.0),
    ("gpu_rx6750xt",        "rx 6750 xt graphics card",             110.0,  380.0),
    ("gpu_rx6800",          "rx 6800 16gb graphics card",           150.0,  500.0),
    ("gpu_rx6800xt",        "rx 6800 xt graphics card",             160.0,  550.0),
    ("gpu_rx6900xt",        "rx 6900 xt graphics card",             180.0,  600.0),
    # AMD RX 7xxx
    ("gpu_rx7600",          "rx 7600 8gb graphics card",            120.0,  380.0),
    ("gpu_rx7700xt",        "rx 7700 xt graphics card",             150.0,  450.0),
    ("gpu_rx7800xt",        "rx 7800 xt graphics card",             180.0,  500.0),
    ("gpu_rx7900xt",        "rx 7900 xt graphics card",             250.0,  700.0),
    ("gpu_rx7900xtx",       "rx 7900 xtx graphics card",           280.0,  800.0),
]

# Bare gaming PC (no GPU, working, just CPU + RAM + storage) sold prices.
# Used to build CPU_BASE_RESALE dynamically.
CPU_SYSTEM_QUERIES: list[tuple[str, str, float, float]] = [
    # Intel 8th-10th gen (AM4-era — common flip source)
    ("sys_i5_8",       "gaming pc i5 8400 desktop tower",       60.0,  300.0),
    ("sys_i7_8",       "gaming pc i7 8700 desktop tower",       80.0,  350.0),
    ("sys_i5_9",       "gaming pc i5 9600 desktop tower",       80.0,  320.0),
    ("sys_i7_9",       "gaming pc i7 9700 desktop tower",      100.0,  380.0),
    ("sys_i9_9",       "gaming pc i9 9900 desktop tower",      120.0,  420.0),
    ("sys_i5_10",      "gaming pc i5 10400 desktop tower",     100.0,  360.0),
    ("sys_i7_10",      "gaming pc i7 10700 desktop tower",     120.0,  420.0),
    # Intel 12th-13th gen (LGA1700 — growing used market)
    ("sys_i5_12",      "gaming pc i5 12400 desktop tower",     150.0,  450.0),
    ("sys_i7_12",      "gaming pc i7 12700 desktop tower",     180.0,  550.0),
    ("sys_i5_13",      "gaming pc i5 13600 desktop tower",     180.0,  550.0),
    ("sys_i7_13",      "gaming pc i7 13700 desktop tower",     220.0,  650.0),
    # Intel 14th gen (LGA1700 — premium tier)
    ("sys_i5_14",      "gaming pc i5 14600 desktop tower",     200.0,  600.0),
    ("sys_i7_14",      "gaming pc i7 14700 desktop tower",     250.0,  750.0),
    # AMD Ryzen 3000 (AM4)
    ("sys_r5_3600",    "gaming pc ryzen 5 3600 desktop",       100.0,  350.0),
    ("sys_r7_3700",    "gaming pc ryzen 7 3700x desktop",      120.0,  400.0),
    ("sys_r9_3900",    "gaming pc ryzen 9 3900x desktop",      140.0,  480.0),
    # AMD Ryzen 5000 (AM4 — primary flip target)
    ("sys_r5_5600",    "gaming pc ryzen 5 5600 desktop",       130.0,  420.0),
    ("sys_r7_5800",    "gaming pc ryzen 7 5800x desktop",      160.0,  500.0),
    ("sys_r9_5900",    "gaming pc ryzen 9 5900x desktop",      190.0,  580.0),
    # AMD Ryzen 7000 (AM5 — DDR5 platform, higher value tier)
    ("sys_r5_7600",    "gaming pc ryzen 5 7600 desktop",       200.0,  580.0),
    ("sys_r7_7700",    "gaming pc ryzen 7 7700x desktop",      250.0,  700.0),
    ("sys_r9_7900",    "gaming pc ryzen 9 7900x desktop",      300.0,  850.0),
    ("sys_r9_7950",    "gaming pc ryzen 9 7950x desktop",      380.0, 1100.0),
    # AMD Ryzen 9000 (AM5 — newest gen)
    ("sys_r5_9600",    "gaming pc ryzen 5 9600x desktop",      220.0,  650.0),
    ("sys_r7_9700",    "gaming pc ryzen 7 9700x desktop",      280.0,  780.0),
]

# Standalone component sold prices — for accessories and case resale benchmarks.
# These tell us both what buyers pay AND let us sanity-check our sourcing costs.
ACCESSORY_QUERIES: list[tuple[str, str, float, float]] = [
    # Cases — what themed RGB cases actually sell for second-hand
    ("resale_case_atx_rgb",     "rgb gaming pc case atx used",              20.0,  120.0),
    ("resale_case_mesh_argb",   "mesh argb gaming case used",               20.0,  130.0),
    ("resale_case_mini_itx",    "mini itx gaming case used",                15.0,  100.0),
    # Peripherals — resale value (what buyers pay on eBay UK)
    ("resale_keyboard_rgb",     "rgb gaming keyboard mechanical used",       10.0,   80.0),
    ("resale_mouse_gaming",     "gaming mouse used",                          5.0,   60.0),
    ("resale_headset_gaming",   "gaming headset used",                        8.0,   70.0),
    ("resale_monitor_1080p",    "24 inch 1080p 144hz gaming monitor used",   40.0,  220.0),
    ("resale_monitor_1440p",    "27 inch 1440p 144hz gaming monitor used",   70.0,  380.0),
    # AM5 components standalone (what they sell for if listed separately)
    ("resale_mobo_am5_b650",    "am5 b650 motherboard used",                 60.0,  220.0),
    ("resale_mobo_am5_x670",    "am5 x670 motherboard used",                 90.0,  350.0),
    ("resale_mobo_am4_b550",    "am4 b550 motherboard used",                 30.0,  160.0),
    ("resale_mobo_am4_x570",    "am4 x570 motherboard used",                 40.0,  220.0),
    # DDR5 kits standalone resale
    ("resale_ram_32gb_ddr5",    "32gb ddr5 desktop ram kit used",            40.0,  400.0),
    ("resale_ram_64gb_ddr5",    "64gb ddr5 desktop ram kit used",            70.0,  600.0),
    # DDR4 kits standalone resale
    ("resale_ram_32gb_ddr4",    "32gb ddr4 desktop ram kit used",            30.0,  350.0),
    ("resale_ram_64gb_ddr4",    "64gb ddr4 desktop ram kit used",            50.0,  500.0),
    # Cooling
    ("resale_aio_120mm",        "120mm aio liquid cpu cooler used",          15.0,   90.0),
    ("resale_aio_240mm",        "240mm aio liquid cpu cooler used",          20.0,  130.0),
]


async def _fetch_median_sold(
    client: httpx.AsyncClient,
    query: str,
    floor: float,
    ceil: float,
) -> float | None:
    """Scrape eBay UK completed/sold listings and return the median price."""
    params = {
        "_nkw":        query,
        "LH_Sold":     "1",
        "LH_Complete": "1",
        "_sop":        "12",
        "LH_PrefLoc":  "1",
        "_ipg":        "60",
    }
    headers = {
        "User-Agent":       _ua.random,
        "Accept-Language":  "en-GB,en;q=0.9",
        "Accept":           "text/html,application/xhtml+xml",
    }
    try:
        resp = await client.get(
            "https://www.ebay.co.uk/sch/i.html",
            params=params,
            headers=headers,
            timeout=20,
        )
        if resp.status_code != 200 or len(resp.text) < 1000:
            return None

        soup = BeautifulSoup(resp.text, "lxml")
        prices: list[float] = []

        for item in soup.select(".s-item:not(.s-item--placeholder)"):
            bid_el = item.select_one(".s-item__bids, .x-bid-count, [class*='bid--']")
            if bid_el and re.search(r"\d+\s*bid", bid_el.get_text(), re.I):
                continue
            price_el = (
                item.select_one(".s-item__price .POSITIVE")
                or item.select_one(".s-item__price")
            )
            if not price_el:
                continue
            text = price_el.get_text(strip=True)
            if re.search(r"\bto\b|–|—", text, re.I):
                continue
            m = re.search(r"[\d,]+\.?\d*", text.replace(",", ""))
            if not m:
                continue
            p = float(m.group(0))
            if floor <= p <= ceil:
                prices.append(p)

        if len(prices) < 3:
            return None

        return round(median(prices), 2)

    except Exception as exc:
        log.warning("price_refresh.fetch_failed", query=query, error=str(exc))
        return None


async def _run_batch(
    client: httpx.AsyncClient,
    queries: list[tuple[str, str, float, float]],
    results: dict,
    failed: list[str],
    pace_seconds: float = 1.5,
) -> None:
    for key, query, floor, ceil in queries:
        price = await _fetch_median_sold(client, query, floor, ceil)
        if price is not None:
            results[key] = price
            log.info("price_refresh.fetched", key=key, price=price)
        else:
            failed.append(key)
            log.warning("price_refresh.no_comps", key=key, query=query)
        await asyncio.sleep(pace_seconds)


async def run_price_refresh() -> dict:
    """
    Fetch live eBay UK sold prices for all component classes and write
    data/price_benchmarks.json. Called daily by the scheduler.
    """
    log.info("price_refresh.start")
    updated: dict[str, float] = {}
    failed: list[str] = []

    # Preserve previous values for any labels we can't fetch this run
    existing: dict = {}
    if _BENCHMARKS_FILE.exists():
        try:
            existing = json.loads(_BENCHMARKS_FILE.read_text(encoding="utf-8"))
        except Exception:
            pass

    async with httpx.AsyncClient(follow_redirects=True) as client:
        await _run_batch(client, BUDGET_COMPONENT_QUERIES, updated, failed)
        await _run_batch(client, GPU_RESALE_QUERIES, updated, failed)
        await _run_batch(client, CPU_SYSTEM_QUERIES, updated, failed)
        await _run_batch(client, ACCESSORY_QUERIES, updated, failed)

    if updated:
        merged = {**existing, **updated}
        merged["refreshed_at"] = time.time()
        merged["refreshed_at_iso"] = datetime.utcnow().isoformat() + "Z"
        merged["updated_count"] = len(updated)
        merged["failed_count"] = len(failed)

        _BENCHMARKS_FILE.parent.mkdir(parents=True, exist_ok=True)
        _BENCHMARKS_FILE.write_text(
            json.dumps(merged, indent=2, ensure_ascii=True),
            encoding="utf-8",
        )
        log.info(
            "price_refresh.saved",
            updated=len(updated),
            failed=len(failed),
            file=str(_BENCHMARKS_FILE),
        )

    return {
        "ok": True,
        "updated": updated,
        "failed": failed,
        "file": str(_BENCHMARKS_FILE),
    }


def load_benchmarks() -> dict[str, float]:
    """
    Load the last-written price benchmarks.
    Returns {} if the file is missing or older than 48 hours.
    """
    try:
        if not _BENCHMARKS_FILE.exists():
            return {}
        data = json.loads(_BENCHMARKS_FILE.read_text(encoding="utf-8"))
        refreshed_at = data.get("refreshed_at", 0)
        age_hours = (time.time() - refreshed_at) / 3600
        if age_hours > 48:
            log.warning("price_refresh.benchmarks_stale", age_hours=round(age_hours, 1))
            return {}
        return {k: v for k, v in data.items() if isinstance(v, (int, float))}
    except Exception as exc:
        log.warning("price_refresh.load_failed", error=str(exc))
        return {}
