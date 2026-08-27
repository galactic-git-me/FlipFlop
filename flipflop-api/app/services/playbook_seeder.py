"""
Playbook Seeder — five canonical Curated Build strategies, linked to live benchmarks.

Safe to run multiple times:
  - Retires removed playbooks (Mainstream Gamer, RGB Showcase, Competitive Gaming, Premium Showcase)
  - Renames where applicable (Developer Workstation → Dev Workstation)
  - Inserts missing playbooks
  - Updates pricing_model / profit_model of ALL active playbooks from live benchmarks
"""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.playbook import Playbook, PlaybookStatus

# ─────────────────────────────────────────────────────────────────────────────
# Live benchmark fallbacks — calibrated June 2026 UK eBay sold prices.
# The price_refresh.py job writes better live values nightly; these are the
# safety net so profit estimates are never zero.
# ─────────────────────────────────────────────────────────────────────────────
_STATIC_BM: dict[str, float] = {
    # Component sourcing costs (what WE pay when buying to add to a build)
    "cost_ram_16gb_ddr4":  30,
    "cost_ram_32gb_ddr4":  55,
    "cost_ram_64gb_ddr4":  90,
    "cost_ram_32gb_ddr5":  75,
    "cost_ram_64gb_ddr5": 130,
    "cost_gpu_rtx3060":   220,
    "cost_gpu_rtx4060":   270,
    "cost_gpu_rx6700xt":  195,
    "cost_ssd_1tb_nvme":   65,
    "cost_ssd_2tb_nvme":  100,
    "cost_psu_650w":       55,
    "cost_psu_750w":       70,
    "cost_case_rgb_atx":   70,
    "cost_mobo_am5_b650": 130,
    "cost_mobo_am4_b550":  70,
    # GPU standalone resale (eBay UK sold median — what a GPU card alone sells for)
    "gpu_gtx1660super":   120,
    "gpu_rtx2060":        150,
    "gpu_rtx3060":        230,
    "gpu_rtx3060ti":      270,
    "gpu_rtx3070":        310,
    "gpu_rtx3080":        400,
    "gpu_rtx3090":        520,
    "gpu_rtx4060":        280,
    "gpu_rtx4060ti":      320,
    "gpu_rtx4070":        400,
    "gpu_rtx4080":        700,
    "gpu_rtx4090":       1400,
    "gpu_rx6600xt":       155,
    "gpu_rx6700xt":       210,
    "gpu_rx7900xtx":      600,
    # Bare-system resale (complete system, that CPU, 16-32 GB RAM, NVMe, no discrete GPU)
    "sys_i5_8":           100,
    "sys_i5_9":           120,
    "sys_i5_10":          140,
    "sys_i5_12":          185,
    "sys_r5_5600":        165,
    "sys_r7_5700":        205,
    "sys_r9_5900":        260,
    "sys_r5_7600":        230,
    "sys_r7_7700":        290,
    "sys_r9_7900":        380,
    "sys_r7_9700":        320,
}


def _bm(benchmarks: dict, key: str) -> float:
    return float(benchmarks.get(key) or _STATIC_BM.get(key, 0.0))


def _fees(sell: float) -> float:
    """eBay managed-payments fee (12.8%) + typical postage + prep overhead."""
    return sell * 0.128 + 35.0


def compute_live_economics(name: str, benchmarks: dict) -> dict:
    """
    Return live-computed pricing_model + profit_model for a named playbook.
    Uses live benchmarks where available, falls back to _STATIC_BM.
    Called at seed time AND injected into every API response so prices
    always reflect the latest eBay UK sold data.
    """
    b = lambda k: _bm(benchmarks, k)

    if name == "Budget Gamer":
        # Source: GPU-less i5-8/9/10 system + add RTX 3060 12 GB
        gpu = b("cost_gpu_rtx3060")
        ram = b("cost_ram_32gb_ddr4")
        ssd = b("cost_ssd_1tb_nvme")
        psu = b("cost_psu_650w")
        # Base system buy target (GPU-less, underpriced vs market)
        base_buy = b("sys_i5_9") * 0.70
        cost_exp = base_buy + gpu + ram * 0.40 + ssd * 0.50 + psu * 0.45
        cost_min = base_buy * 0.80 + gpu * 0.90
        cost_max = base_buy * 1.20 + gpu * 1.08 + ram * 0.70 + ssd + psu
        # Sell: gaming PC with RTX 3060 commands ~1.95× standalone GPU value
        sell_exp = 155 + b("gpu_rtx3060") * 1.95
        sell_min = sell_exp * 0.88
        sell_max = sell_exp * 1.12

    elif name == "Mid-level Gamer":
        # Source: Ryzen 5 5600 / i5-12 system + RTX 3070 or RX 6700 XT
        gpu_hi = b("gpu_rtx3070")          # RTX 3070 standalone
        gpu_lo = b("cost_gpu_rx6700xt")    # RX 6700 XT sourcing cost
        gpu = (gpu_hi + gpu_lo) / 2        # blend: some use RTX 3070, some RX 6700 XT
        ram = b("cost_ram_32gb_ddr4")
        ssd = b("cost_ssd_1tb_nvme")
        psu = b("cost_psu_750w")
        base_buy = b("sys_r5_5600") * 0.65
        cost_exp = base_buy + gpu + ram * 0.55 + ssd * 0.60 + psu * 0.50
        cost_min = base_buy * 0.80 + gpu_lo * 0.90
        cost_max = base_buy * 1.20 + gpu_hi * 1.05 + ram * 0.80 + ssd + psu
        # 1440p capable PC: 1.85× RTX 3070 standalone
        sell_exp = 180 + b("gpu_rtx3070") * 1.85
        sell_min = sell_exp * 0.87
        sell_max = sell_exp * 1.13

    elif name == "High-end Gamer":
        # Source: AM5 Ryzen 7 7700 / i9 system + RTX 4080
        gpu = b("gpu_rtx4080")
        ram = b("cost_ram_32gb_ddr5")
        ssd = b("cost_ssd_2tb_nvme")
        psu = b("cost_psu_750w")
        mobo = b("cost_mobo_am5_b650")
        base_buy = b("sys_r7_7700") * 0.65
        cost_exp = base_buy + gpu + ram * 0.70 + ssd * 0.60 + psu * 0.40 + mobo * 0.30
        cost_min = base_buy * 0.80 + gpu * 0.92
        cost_max = base_buy * 1.15 + gpu * 1.06 + ram + ssd + psu + mobo * 0.50
        # 4K / ultra-settings PC: ~2.1× RTX 4080 standalone
        sell_exp = 350 + b("gpu_rtx4080") * 2.10
        sell_min = sell_exp * 0.85
        sell_max = sell_exp * 1.15

    elif name == "Ultra-Budget Flip":
        # Buy job-lots of ex-office PCs (5-unit lot model), clean and sell individually
        ssd = b("cost_ssd_1tb_nvme")
        per_unit_buy = 40.0           # £40/unit average when buying bulk lots
        per_unit_extras = ssd * 0.30  # ~30% of units need an SSD added
        per_unit_overhead = 12.0      # Windows licence + cleaning
        cost_per_unit = per_unit_buy + per_unit_extras + per_unit_overhead
        lot_size_exp = 6              # typical 6-unit lot
        cost_exp = cost_per_unit * lot_size_exp
        cost_min = (per_unit_buy * 0.75 + per_unit_overhead) * lot_size_exp
        cost_max = (per_unit_buy * 1.25 + ssd * 0.50 + per_unit_overhead) * lot_size_exp
        # Sell each unit at £120-160 via eBay + Facebook/Gumtree mix
        sell_per_unit = 135.0
        sell_exp = sell_per_unit * lot_size_exp
        sell_min = 110.0 * lot_size_exp
        sell_max = 160.0 * lot_size_exp

    elif name == "Office Station Flip":
        # Source: i5-8/9/10 SFF/tower office PC, add SSD and RAM
        ssd = b("cost_ssd_1tb_nvme")
        ram = b("cost_ram_32gb_ddr4")
        base_buy = b("sys_i5_10") * 0.58
        cost_exp = base_buy + ssd * 0.50 + ram * 0.40
        cost_min = b("sys_i5_8") * 0.55 + ssd * 0.30
        cost_max = b("sys_i5_12") * 0.65 + ssd + ram * 0.60
        # Clean office PC with SSD, Windows 11, 32 GB: ~1.4× base system sell value
        sell_exp = 80 + b("sys_i5_10") * 1.42
        sell_min = 60 + b("sys_i5_9") * 1.30
        sell_max = 100 + b("sys_i5_12") * 1.55

    elif name == "Content Creator":
        # Source: Ryzen 9 5900X workstation + RTX 3080
        gpu = b("gpu_rtx3080")
        ram = b("cost_ram_64gb_ddr4")
        ssd = b("cost_ssd_2tb_nvme")
        psu = b("cost_psu_750w")
        base_buy = b("sys_r9_5900") * 0.68
        cost_exp = base_buy + gpu + ram * 0.65 + ssd * 0.70 + psu * 0.45
        cost_min = base_buy * 0.82 + gpu * 0.90 + ssd * 0.50
        cost_max = base_buy * 1.15 + gpu * 1.06 + ram + ssd + psu
        # Video editing / streaming PC: 2.0× RTX 3080 standalone
        sell_exp = 250 + b("gpu_rtx3080") * 2.0
        sell_min = sell_exp * 0.86
        sell_max = sell_exp * 1.14

    elif name == "AI Workstation":
        # Source: high-core system + RTX 3090 (24 GB VRAM for local LLMs)
        gpu = b("gpu_rtx3090")
        ram = b("cost_ram_64gb_ddr4")
        ssd = b("cost_ssd_2tb_nvme")
        psu = b("cost_psu_750w")
        base_buy = b("sys_r9_5900") * 0.65
        cost_exp = base_buy + gpu + ram * 0.80 + ssd * 0.70 + psu * 0.50
        cost_min = base_buy * 0.80 + gpu * 0.90
        cost_max = base_buy * 1.15 + gpu * 1.08 + ram + ssd + psu
        # AI hobbyist / dev buyers pay premium for VRAM: 2.3× RTX 3090 standalone
        sell_exp = 300 + b("gpu_rtx3090") * 2.30
        sell_min = sell_exp * 0.84
        sell_max = sell_exp * 1.16

    elif name == "Dev Workstation":
        # Source: multi-core workstation (Ryzen 9 / Xeon) + 64 GB RAM, no big GPU
        ram = b("cost_ram_64gb_ddr4")
        ssd = b("cost_ssd_2tb_nvme")
        psu = b("cost_psu_650w")
        base_buy = b("sys_r7_5700") * 0.70
        cost_exp = base_buy + ram * 0.80 + ssd * 0.70 + psu * 0.30
        cost_min = base_buy * 0.78 + ram * 0.55 + ssd * 0.50
        cost_max = base_buy * 1.18 + ram + ssd + psu
        # Dev workstation (high RAM, fast NVMe, good CPU, no GPU): 1.9× sys_r9
        sell_exp = 150 + b("sys_r9_5900") * 1.85
        sell_min = sell_exp * 0.87
        sell_max = sell_exp * 1.13

    elif name == "Student Build":
        # Source: i5-8/9 office PC, add NVMe, clean install Windows
        ssd = b("cost_ssd_1tb_nvme")
        ram = b("cost_ram_32gb_ddr4")
        base_buy = b("sys_i5_9") * 0.62
        cost_exp = base_buy + ssd * 0.55 + ram * 0.30
        cost_min = b("sys_i5_8") * 0.55 + ssd * 0.35
        cost_max = b("sys_i5_10") * 0.68 + ssd + ram * 0.50
        # Student-budget desktop: 1.65× bare system sell value
        sell_exp = 75 + b("sys_i5_9") * 1.65
        sell_min = 60 + b("sys_i5_8") * 1.50
        sell_max = 95 + b("sys_i5_10") * 1.80

    elif name == "Family PC":
        # Source: Ryzen 5 5600 / i5-12th mid-range system, light gaming optional
        ssd = b("cost_ssd_1tb_nvme")
        ram = b("cost_ram_32gb_ddr4")
        gpu_opt = b("cost_gpu_rtx4060") * 0.28  # only ~28% add a light GPU
        base_buy = b("sys_r5_5600") * 0.68
        cost_exp = base_buy + gpu_opt + ssd * 0.50 + ram * 0.45
        cost_min = b("sys_i5_10") * 0.65 + ssd * 0.35
        cost_max = b("sys_r5_5600") * 1.10 + b("cost_gpu_rtx4060") * 0.50 + ssd + ram
        # Family desktop (capable, reliable): 1.55× Ryzen 5 5600 bare system
        sell_exp = 155 + b("sys_r5_5600") * 1.55
        sell_min = sell_exp * 0.87
        sell_max = sell_exp * 1.13

    elif name == "Gift-from-parents PC":
        # Source: modern CPU system + RTX 4060 (new-gen appeal), RGB case
        gpu = b("cost_gpu_rtx4060")
        ram = b("cost_ram_32gb_ddr4")
        ssd = b("cost_ssd_1tb_nvme")
        case = b("cost_case_rgb_atx")
        psu = b("cost_psu_650w")
        base_buy = b("sys_i5_12") * 0.68
        cost_exp = base_buy + gpu + ram * 0.45 + ssd * 0.50 + case * 0.55 + psu * 0.40
        cost_min = base_buy * 0.82 + gpu * 0.90
        cost_max = base_buy * 1.15 + gpu * 1.06 + ram * 0.70 + ssd + case + psu
        # Gift-appeal RTX 4060 gaming PC (new-gen GPU, looks impressive): 2.1× RTX 4060 standalone
        sell_exp = 160 + b("gpu_rtx4060") * 2.10
        sell_min = sell_exp * 0.88
        sell_max = sell_exp * 1.12

    else:
        return {}

    # Compute profit (using expected sell - expected cost as the base)
    fees_exp = _fees(sell_exp)
    fees_min = _fees(sell_min)
    fees_max = _fees(sell_max)

    profit_exp  = sell_exp  - fees_exp  - cost_exp
    # Best case: sell high, cost low
    profit_max  = sell_max  - fees_max  - cost_min
    # Worst case: sell low, cost high
    profit_min  = sell_min  - fees_min  - cost_max
    # Floor at 0 — we walk away from a deal that loses money
    profit_min  = max(0.0, profit_min)

    roi_pct = round((profit_exp / cost_exp) * 100) if cost_exp else 0

    return {
        "pricing_model": {
            "minimum_build_cost":  round(cost_min),
            "expected_build_cost": round(cost_exp),
            "maximum_build_cost":  round(cost_max),
            "sell_target_min":     round(sell_min),
            "sell_target_exp":     round(sell_exp),
            "sell_target_max":     round(sell_max),
        },
        "profit_model": {
            "minimum_profit":  round(profit_min),
            "expected_profit": round(profit_exp),
            "maximum_profit":  round(profit_max),
            "expected_roi_pct": roi_pct,
        },
    }


# ─────────────────────────────────────────────────────────────────────────────
# Qualitative playbook definitions — the parts that don't change with prices.
# pricing_model / profit_model are left empty here and filled in by
# seed_playbooks() using compute_live_economics() from live benchmarks.
# ─────────────────────────────────────────────────────────────────────────────
_INITIAL_PLAYBOOKS: list[dict] = [
    # ── 1. Budget Gamer ──────────────────────────────────────────────────────
    {
        "name": "Budget Gamer",
        "emoji": "🎮",
        "status": "active",
        "target_use_case": "gaming",
        "target_customer": "Kids / Teens / First-time gamers",
        "what_they_use_it_for": "Fortnite, Minecraft, Roblox, Valorant, Discord, light streaming",
        "what_they_want_from_build": "Runs games at 1080p without breaking the bank. Looks like a gaming PC.",
        "critical_success_factors": ["RTX 3060 12GB (sweet-spot 1080p)", "i5 8th-12th gen", "32 GB DDR4", "1 TB NVMe", "650 W PSU"],
        "profit_opportunity_score": 5.0,
        "market_size_score": 9.0,
        "resellability_score": 9.0,
        "liquidity_score": 9.0,
        "risk_score": 3.0,
        "market_growth_direction": "Stable",
        "requirements": {"cpu_min_tier": "i5", "ram_min_gb": 16, "gpu_required": True, "psu_required": True},
        "search_strategy": {
            "keywords": ["gaming pc no gpu", "gaming pc rtx 3060", "gaming pc gtx 1660", "budget gaming desktop", "i5 gaming pc"],
            "price_min": 60, "price_max": 200, "listing_types": ["buy_it_now", "auction"],
        },
        "profit_strategy": {
            "target_profit_gbp": 100, "target_margin_pct": 38,
            "sell_platform": "eBay", "flip_structure": "buy_upgrade_sell",
            "notes": "Buy GPU-less. Source RTX 3060 separately. Top-up RAM to 32 GB, add NVMe SSD.",
        },
        "ideal_build": {
            "cpu": {
                "candidate_models": ["i5-10400F", "i5-10600", "i5-9400F", "Ryzen 5 5600"],
                "search_terms": ["i5 10400 gaming pc no gpu", "i5 9400 desktop no gpu"],
                "negative_search_terms": ["faulty", "no power", "for parts"],
            },
            "gpu": {
                "candidate_models": ["RTX 3060 12GB", "RX 6600 XT"],
                "search_terms": ["rtx 3060 12gb", "rx 6600 xt"],
                "negative_search_terms": ["faulty", "mining", "blower"],
            },
            "ram": {
                "candidate_models": ["16 GB DDR4 3200 MHz top-up to 32 GB"],
                "search_terms": ["16gb ddr4 3200", "ddr4 ram kit"],
                "negative_search_terms": ["faulty", "untested"],
            },
            "storage": {
                "candidate_models": ["1 TB NVMe SSD"],
                "search_terms": ["1tb nvme ssd m.2"],
                "negative_search_terms": [],
            },
            "psu": {
                "candidate_models": ["550 W 80+ Bronze", "650 W 80+ Bronze"],
                "search_terms": ["650w psu bronze", "550w power supply"],
                "negative_search_terms": ["faulty", "no cable"],
            },
        },
        "seasonality": {
            "jan": 4, "feb": 3, "mar": 4, "apr": 4, "may": 5, "jun": 5,
            "jul": 5, "aug": 6, "sep": 6, "oct": 7, "nov": 9, "dec": 10,
            "peak_months": ["november", "december"], "slow_months": ["january", "february"],
            "current_position": "mid_season", "days_until_peak": 150,
        },
        "pricing_model": {}, "profit_model": {},
        "upgrade_strategy": {}, "upsell_strategy": {}, "component_catalogue": {},
    },

    # ── 2. Mid-level Gamer ───────────────────────────────────────────────────
    {
        "name": "Mid-level Gamer",
        "emoji": "🖥️",
        "status": "active",
        "target_use_case": "gaming",
        "target_customer": "18-35 gamers, upgrade-hungry buyers",
        "what_they_use_it_for": "1440p gaming, modern AAA titles, streaming, content consumption",
        "what_they_want_from_build": "1440p capable GPU, Ryzen 5000 / Intel 12th+ CPU, 32 GB RAM, NVMe, looks decent",
        "critical_success_factors": ["RTX 3070 / RX 6700 XT (1440p capable)", "Ryzen 5 5600 or Intel 12th base", "32 GB DDR4", "1 TB NVMe"],
        "profit_opportunity_score": 5.0,
        "market_size_score": 8.0,
        "resellability_score": 8.0,
        "liquidity_score": 7.0,
        "risk_score": 4.0,
        "market_growth_direction": "Growing",
        "requirements": {"cpu_min_tier": "i5", "ram_min_gb": 16, "gpu_required": True, "psu_required": True},
        "search_strategy": {
            "keywords": ["gaming pc rtx 3070", "gaming pc rx 6700", "gaming pc rtx 3080", "1440p gaming desktop"],
            "price_min": 150, "price_max": 380, "listing_types": ["buy_it_now", "auction"],
        },
        "profit_strategy": {
            "target_profit_gbp": 150, "target_margin_pct": 36,
            "sell_platform": "eBay", "flip_structure": "buy_upgrade_sell",
            "notes": "R5 5600 base + RX 6700 XT is the best value combo. RTX 3070 for buyers who want Nvidia.",
        },
        "ideal_build": {
            "cpu": {
                "candidate_models": ["Ryzen 5 5600", "Ryzen 5 5600X", "i5-12400F", "i5-12600K"],
                "search_terms": ["ryzen 5 5600 gaming pc", "i5 12400 desktop no gpu"],
                "negative_search_terms": ["faulty", "for parts"],
            },
            "gpu": {
                "candidate_models": ["RTX 3070", "RX 6700 XT", "RTX 3070 Ti"],
                "search_terms": ["rtx 3070", "rx 6700 xt", "rtx 3070 ti"],
                "negative_search_terms": ["mining", "faulty", "blower"],
            },
            "ram": {
                "candidate_models": ["32 GB DDR4 3200 MHz", "32 GB DDR4 3600 MHz"],
                "search_terms": ["32gb ddr4 kit", "ddr4 3600 32gb"],
                "negative_search_terms": [],
            },
            "storage": {
                "candidate_models": ["1 TB NVMe SSD"],
                "search_terms": ["1tb nvme m.2 ssd"],
                "negative_search_terms": [],
            },
            "psu": {
                "candidate_models": ["650 W 80+ Gold", "750 W 80+ Gold"],
                "search_terms": ["650w gold psu", "750w modular psu"],
                "negative_search_terms": ["faulty"],
            },
        },
        "seasonality": {
            "jan": 5, "feb": 5, "mar": 6, "apr": 6, "may": 7, "jun": 7,
            "jul": 7, "aug": 7, "sep": 7, "oct": 8, "nov": 10, "dec": 9,
            "peak_months": ["october", "november"], "slow_months": ["january", "february"],
            "current_position": "mid_season", "days_until_peak": 120,
        },
        "pricing_model": {}, "profit_model": {},
        "upgrade_strategy": {}, "upsell_strategy": {}, "component_catalogue": {},
    },

    # ── 3. High-end Gamer ────────────────────────────────────────────────────
    {
        "name": "High-end Gamer",
        "emoji": "👑",
        "status": "active",
        "target_use_case": "gaming",
        "target_customer": "Serious gamers, 4K buyers, enthusiasts",
        "what_they_use_it_for": "4K gaming, VR, high-refresh 1440p, prestige ownership",
        "what_they_want_from_build": "RTX 4080 or better, AM5 platform (DDR5), premium case, best-in-class",
        "critical_success_factors": ["RTX 4080 / 4090 (4K capable)", "AM5 / Intel 13th-14th gen", "DDR5 RAM", "2 TB NVMe"],
        "profit_opportunity_score": 3.0,
        "market_size_score": 4.0,
        "resellability_score": 5.0,
        "liquidity_score": 3.0,
        "risk_score": 7.0,
        "market_growth_direction": "Stable",
        "requirements": {"cpu_min_tier": "i9", "ram_min_gb": 32, "gpu_required": True, "psu_required": True},
        "search_strategy": {
            "keywords": ["rtx 4080 gaming pc", "rtx 4090 desktop", "high end gaming pc", "am5 gaming pc"],
            "price_min": 500, "price_max": 2000, "listing_types": ["buy_it_now"],
        },
        "profit_strategy": {
            "target_profit_gbp": 280, "target_margin_pct": 27,
            "sell_platform": "eBay", "flip_structure": "buy_upgrade_sell",
            "notes": "High value, slower sales. Premium listing photos essential. Detailed spec sheet drives price.",
        },
        "ideal_build": {
            "cpu": {
                "candidate_models": ["Ryzen 7 7700X", "Ryzen 9 7900X", "i9-13900K", "i9-14900K"],
                "search_terms": ["ryzen 7 7700x gaming pc", "i9 13900k desktop"],
                "negative_search_terms": ["faulty", "for parts"],
            },
            "gpu": {
                "candidate_models": ["RTX 4080", "RTX 4080 Super", "RTX 4090"],
                "search_terms": ["rtx 4080", "rtx 4090"],
                "negative_search_terms": ["faulty", "mining"],
            },
            "ram": {
                "candidate_models": ["32 GB DDR5 6000 MHz", "64 GB DDR5"],
                "search_terms": ["32gb ddr5 6000mhz", "ddr5 ram kit"],
                "negative_search_terms": [],
            },
            "storage": {
                "candidate_models": ["2 TB NVMe Gen4/5"],
                "search_terms": ["2tb nvme gen4", "2tb m.2 ssd"],
                "negative_search_terms": [],
            },
            "psu": {
                "candidate_models": ["850 W 80+ Gold", "1000 W 80+ Gold"],
                "search_terms": ["850w gold psu", "1000w psu"],
                "negative_search_terms": ["faulty"],
            },
        },
        "seasonality": {
            "jan": 4, "feb": 4, "mar": 4, "apr": 5, "may": 5, "jun": 5,
            "jul": 5, "aug": 5, "sep": 5, "oct": 6, "nov": 9, "dec": 10,
            "peak_months": ["november", "december"], "slow_months": ["january", "march"],
            "current_position": "slow_season", "days_until_peak": 155,
        },
        "pricing_model": {}, "profit_model": {},
        "upgrade_strategy": {}, "upsell_strategy": {}, "component_catalogue": {},
    },

    # ── 4. Ultra-Budget Flip ─────────────────────────────────────────────────
    {
        "name": "Ultra-Budget Flip",
        "emoji": "💰",
        "status": "active",
        "target_use_case": "budget",
        "target_customer": "Facebook Marketplace / Gumtree budget buyers",
        "what_they_use_it_for": "Basic web, email, kids' homework, Zoom calls, Netflix",
        "what_they_want_from_build": "Just works, cheap. SSD is a bonus. Under £150.",
        "critical_success_factors": ["Under £150 sell price", "Working condition", "SSD preferred", "Clean Windows install"],
        "profit_opportunity_score": 4.0,
        "market_size_score": 10.0,
        "resellability_score": 8.0,
        "liquidity_score": 10.0,
        "risk_score": 2.0,
        "market_growth_direction": "Stable",
        "requirements": {"cpu_min_tier": "i3", "ram_min_gb": 4, "gpu_required": False, "psu_required": True},
        "search_strategy": {
            "keywords": ["job lot pcs", "bulk office pcs", "ex lease pc", "joblot computers", "pc bundle clearance", "office pc lot"],
            "price_min": 5, "price_max": 50, "listing_types": ["buy_it_now", "auction"],
        },
        "profit_strategy": {
            "target_profit_gbp": 55, "target_margin_pct": 60,
            "sell_platform": "eBay + Facebook Marketplace",
            "flip_structure": "buy_clean_sell",
            "notes": "Buy lots of 5-10. Clean and sell individually at £110-160. Local cash sales avoid eBay fees.",
        },
        "ideal_build": {
            "cpu": {
                "candidate_models": ["i3-8100", "i5-7500", "i5-8400", "i3-10100"],
                "search_terms": ["job lot pcs office", "bulk pcs clearance", "ex lease desktop lot"],
                "negative_search_terms": ["scrap only", "water damaged", "spares/repairs only"],
            },
            "ram": {
                "candidate_models": ["8 GB DDR4", "4 GB DDR4"],
                "search_terms": ["8gb ddr4", "4gb ddr4"],
                "negative_search_terms": [],
            },
            "storage": {
                "candidate_models": ["240 GB SSD", "120 GB SSD"],
                "search_terms": ["240gb ssd sata", "120gb ssd lot"],
                "negative_search_terms": [],
            },
        },
        "seasonality": {
            "jan": 6, "feb": 6, "mar": 7, "apr": 7, "may": 7, "jun": 7,
            "jul": 7, "aug": 8, "sep": 8, "oct": 8, "nov": 9, "dec": 9,
            "peak_months": ["november", "december", "august"], "slow_months": [],
            "current_position": "in_season", "days_until_peak": 0,
        },
        "pricing_model": {}, "profit_model": {},
        "upgrade_strategy": {}, "upsell_strategy": {}, "component_catalogue": {},
    },

    # ── 5. Office Station Flip ───────────────────────────────────────────────
    {
        "name": "Office Station Flip",
        "emoji": "🏢",
        "status": "active",
        "target_use_case": "office",
        "target_customer": "Small businesses, home office workers, freelancers",
        "what_they_use_it_for": "Microsoft Office, Teams, Zoom, Chrome, email, light admin",
        "what_they_want_from_build": "Reliable, fast SSD boot, 32 GB RAM for multitasking, Windows 11 Pro",
        "critical_success_factors": ["i5 8th-12th gen", "32 GB DDR4", "1 TB NVMe SSD", "Clean Windows 11 Pro", "Working USB + display ports"],
        "profit_opportunity_score": 4.0,
        "market_size_score": 7.0,
        "resellability_score": 7.0,
        "liquidity_score": 7.0,
        "risk_score": 3.0,
        "market_growth_direction": "Stable",
        "requirements": {"cpu_min_tier": "i5", "ram_min_gb": 8, "gpu_required": False, "psu_required": True},
        "search_strategy": {
            "keywords": ["HP EliteDesk", "Dell OptiPlex", "Lenovo ThinkCentre", "office pc i5", "ex office desktop"],
            "price_min": 40, "price_max": 130, "listing_types": ["buy_it_now", "auction"],
        },
        "profit_strategy": {
            "target_profit_gbp": 70, "target_margin_pct": 48,
            "sell_platform": "eBay", "flip_structure": "buy_upgrade_sell",
            "notes": "Add NVMe SSD if HDD-only, top up to 32 GB RAM. List as 'office ready', price against £200-350 new.",
        },
        "ideal_build": {
            "cpu": {
                "candidate_models": ["i5-10400", "i5-9400", "i5-8500", "i5-12400"],
                "search_terms": ["dell optiplex i5", "hp elitedesk i5 10th", "lenovo thinkcentre i5"],
                "negative_search_terms": ["faulty", "no power", "no hdd only"],
            },
            "ram": {
                "candidate_models": ["16 GB DDR4", "32 GB DDR4"],
                "search_terms": ["16gb ddr4 desktop", "32gb ddr4"],
                "negative_search_terms": [],
            },
            "storage": {
                "candidate_models": ["500 GB SSD SATA", "1 TB NVMe SSD"],
                "search_terms": ["500gb ssd", "1tb nvme m.2"],
                "negative_search_terms": [],
            },
        },
        "seasonality": {
            "jan": 7, "feb": 7, "mar": 9, "apr": 9, "may": 8, "jun": 8,
            "jul": 6, "aug": 6, "sep": 8, "oct": 8, "nov": 7, "dec": 6,
            "peak_months": ["march", "april", "september"], "slow_months": ["july", "august"],
            "current_position": "in_season", "days_until_peak": 0,
        },
        "pricing_model": {}, "profit_model": {},
        "upgrade_strategy": {}, "upsell_strategy": {}, "component_catalogue": {},
    },

    # ── 6. Content Creator ───────────────────────────────────────────────────
    {
        "name": "Content Creator",
        "emoji": "🎬",
        "status": "active",
        "target_use_case": "workstation",
        "target_customer": "YouTubers, streamers, video editors, Photoshop users",
        "what_they_use_it_for": "Premiere Pro, DaVinci Resolve, OBS, After Effects, Photoshop, streaming",
        "what_they_want_from_build": "Fast multi-core CPU for rendering, RTX GPU for NVENC/HEVC, 64 GB RAM, 2 TB storage",
        "critical_success_factors": ["Ryzen 9 5900X / i9 class CPU", "RTX 3080 (NVENC)", "64 GB RAM", "2 TB fast NVMe"],
        "profit_opportunity_score": 3.0,
        "market_size_score": 6.0,
        "resellability_score": 6.0,
        "liquidity_score": 5.0,
        "risk_score": 4.0,
        "market_growth_direction": "Growing",
        "requirements": {"cpu_min_tier": "i7", "ram_min_gb": 32, "gpu_required": True, "psu_required": True},
        "search_strategy": {
            "keywords": ["content creator pc", "video editing pc", "streaming pc", "ryzen 9 desktop", "i9 desktop workstation"],
            "price_min": 130, "price_max": 450, "listing_types": ["buy_it_now", "auction"],
        },
        "profit_strategy": {
            "target_profit_gbp": 150, "target_margin_pct": 25,
            "sell_platform": "eBay", "flip_structure": "buy_upgrade_sell",
            "notes": "Market is small but buyers pay well for proven configs. Mention software compatibility explicitly.",
        },
        "ideal_build": {
            "cpu": {
                "candidate_models": ["Ryzen 9 5900X", "Ryzen 9 5950X", "i9-10900K", "i9-12900K"],
                "search_terms": ["ryzen 9 5900x desktop", "i9 10900k pc no gpu"],
                "negative_search_terms": ["faulty", "damaged"],
            },
            "gpu": {
                "candidate_models": ["RTX 3080 10GB", "RTX 3080 Ti", "RTX 4070"],
                "search_terms": ["rtx 3080", "rtx 4070", "rtx 3080 ti"],
                "negative_search_terms": ["mining", "faulty"],
            },
            "ram": {
                "candidate_models": ["64 GB DDR4 3200 MHz", "32 GB DDR4 3600 MHz"],
                "search_terms": ["64gb ddr4", "32gb ddr4 3600"],
                "negative_search_terms": [],
            },
            "storage": {
                "candidate_models": ["2 TB NVMe SSD", "2 TB Samsung 980 Pro"],
                "search_terms": ["2tb nvme m.2", "samsung 980 pro 2tb"],
                "negative_search_terms": [],
            },
            "psu": {
                "candidate_models": ["850 W 80+ Gold", "1000 W 80+ Gold"],
                "search_terms": ["850w gold psu", "1000w psu modular"],
                "negative_search_terms": ["faulty"],
            },
        },
        "seasonality": {
            "jan": 5, "feb": 5, "mar": 6, "apr": 7, "may": 7, "jun": 7,
            "jul": 7, "aug": 7, "sep": 7, "oct": 8, "nov": 9, "dec": 8,
            "peak_months": ["october", "november"], "slow_months": ["january", "february"],
            "current_position": "mid_season", "days_until_peak": 120,
        },
        "pricing_model": {}, "profit_model": {},
        "upgrade_strategy": {}, "upsell_strategy": {}, "component_catalogue": {},
    },

    # ── 7. AI Workstation ────────────────────────────────────────────────────
    {
        "name": "AI Workstation",
        "emoji": "🤖",
        "status": "active",
        "target_use_case": "ai_workstation",
        "target_customer": "AI hobbyists, developers running local LLMs, Stable Diffusion users",
        "what_they_use_it_for": "Ollama, Open WebUI, llama.cpp, Stable Diffusion, AI coding agents",
        "what_they_want_from_build": "24 GB+ VRAM (RTX 3090 is the sweet spot), 64 GB+ system RAM, fast CPU",
        "critical_success_factors": ["RTX 3090 (24 GB VRAM — key for 30B models)", "64 GB system RAM", "Ryzen 9 / Xeon CPU", "2 TB+ NVMe"],
        "profit_opportunity_score": 3.0,
        "market_size_score": 7.0,
        "resellability_score": 7.0,
        "liquidity_score": 5.0,
        "risk_score": 4.0,
        "market_growth_direction": "Growing",
        "requirements": {"cpu_min_tier": "i7", "ram_min_gb": 32, "gpu_required": True, "psu_required": True},
        "search_strategy": {
            "keywords": ["rtx 3090 pc", "ai workstation", "local llm pc", "ml workstation", "rtx 3090 desktop"],
            "price_min": 250, "price_max": 900, "listing_types": ["buy_it_now", "auction"],
        },
        "profit_strategy": {
            "target_profit_gbp": 400, "target_margin_pct": 45,
            "sell_platform": "eBay", "flip_structure": "buy_upgrade_sell",
            "notes": "AI market growing fast. VRAM is the value driver. Target AI subs and developer communities. Slow sales — be patient.",
        },
        "ideal_build": {
            "cpu": {
                "candidate_models": ["Ryzen 9 5900X", "Ryzen 9 5950X", "Xeon E5-2690 v4"],
                "search_terms": ["ryzen 9 5900x desktop", "xeon e5 workstation 64gb"],
                "negative_search_terms": ["faulty", "no cpu"],
            },
            "gpu": {
                "candidate_models": ["RTX 3090 24GB", "RTX 3090 Ti"],
                "search_terms": ["rtx 3090 24gb", "rtx 3090 ti"],
                "negative_search_terms": ["faulty", "mining", "blower"],
            },
            "ram": {
                "candidate_models": ["64 GB DDR4 ECC", "64 GB DDR4 3200 MHz"],
                "search_terms": ["64gb ddr4 ecc", "64gb ddr4 server ram"],
                "negative_search_terms": [],
            },
            "storage": {
                "candidate_models": ["2 TB NVMe SSD", "4 TB NVMe SSD"],
                "search_terms": ["2tb nvme", "4tb nvme ssd"],
                "negative_search_terms": [],
            },
            "psu": {
                "candidate_models": ["1000 W 80+ Gold", "1200 W 80+ Platinum"],
                "search_terms": ["1000w psu", "1200w platinum psu"],
                "negative_search_terms": ["faulty"],
            },
        },
        "seasonality": {
            "jan": 7, "feb": 8, "mar": 8, "apr": 9, "may": 9, "jun": 9,
            "jul": 8, "aug": 8, "sep": 8, "oct": 8, "nov": 8, "dec": 7,
            "peak_months": ["april", "may", "june"], "slow_months": ["december"],
            "current_position": "in_peak", "days_until_peak": 0,
        },
        "pricing_model": {}, "profit_model": {},
        "upgrade_strategy": {}, "upsell_strategy": {}, "component_catalogue": {},
    },

    # ── 8. Dev Workstation ───────────────────────────────────────────────────
    {
        "name": "Dev Workstation",
        "emoji": "💻",
        "status": "active",
        "target_use_case": "workstation",
        "target_customer": "Software developers, sysadmins, DevOps engineers",
        "what_they_use_it_for": "Docker, VMs, databases, VS Code, coding agents, CI runners, Node.js, Python",
        "what_they_want_from_build": "Core count, 64 GB+ RAM, fast 2 TB NVMe, reliable CPU, ECC if possible",
        "critical_success_factors": ["8+ core CPU (Ryzen 7 5700X+)", "64 GB DDR4", "2 TB NVMe", "Reliable brand", "Good thermals"],
        "profit_opportunity_score": 3.0,
        "market_size_score": 6.0,
        "resellability_score": 6.0,
        "liquidity_score": 5.0,
        "risk_score": 4.0,
        "market_growth_direction": "Growing",
        "requirements": {"cpu_min_tier": "i7", "ram_min_gb": 32, "gpu_required": False, "psu_required": True},
        "search_strategy": {
            "keywords": ["hp workstation", "dell precision workstation", "hp z440", "hp z640", "ryzen 9 desktop"],
            "price_min": 80, "price_max": 350, "listing_types": ["buy_it_now", "auction"],
        },
        "profit_strategy": {
            "target_profit_gbp": 180, "target_margin_pct": 55,
            "sell_platform": "eBay", "flip_structure": "buy_upgrade_sell",
            "notes": "Dev buyers pay for RAM and storage, not GPU. Mention Docker, VM, CI runner use cases.",
        },
        "ideal_build": {
            "cpu": {
                "candidate_models": ["Ryzen 7 5700X", "Ryzen 9 5900X", "Xeon E5-2690 v4", "i7-10700K"],
                "search_terms": ["ryzen 9 5900x desktop", "hp z440 workstation", "xeon e5 workstation"],
                "negative_search_terms": ["faulty", "damaged"],
            },
            "ram": {
                "candidate_models": ["64 GB DDR4 ECC", "64 GB DDR4", "128 GB DDR4"],
                "search_terms": ["64gb ddr4 ecc", "64gb ddr4 workstation"],
                "negative_search_terms": [],
            },
            "storage": {
                "candidate_models": ["2 TB NVMe SSD", "1 TB NVMe + 2 TB HDD"],
                "search_terms": ["2tb nvme", "1tb nvme ssd"],
                "negative_search_terms": [],
            },
            "psu": {
                "candidate_models": ["750 W 80+ Gold", "850 W 80+ Gold"],
                "search_terms": ["750w gold psu", "850w psu"],
                "negative_search_terms": ["faulty"],
            },
        },
        "seasonality": {
            "jan": 7, "feb": 7, "mar": 8, "apr": 8, "may": 8, "jun": 8,
            "jul": 7, "aug": 7, "sep": 8, "oct": 8, "nov": 7, "dec": 6,
            "peak_months": ["march", "april", "september"], "slow_months": ["december"],
            "current_position": "in_season", "days_until_peak": 0,
        },
        "pricing_model": {}, "profit_model": {},
        "upgrade_strategy": {}, "upsell_strategy": {}, "component_catalogue": {},
    },

    # ── 9. Student Build ─────────────────────────────────────────────────────
    {
        "name": "Student Build",
        "emoji": "🎓",
        "status": "active",
        "target_use_case": "budget",
        "target_customer": "University / sixth-form students",
        "what_they_use_it_for": "Essays, research, Zoom, Discord, Netflix, light gaming",
        "what_they_want_from_build": "Affordable, fast SSD boot, reliable, Windows 11, under £250",
        "critical_success_factors": ["Fast SSD (not HDD)", "16-32 GB RAM", "i5 8th-10th gen", "Clean Windows 11", "Under £250"],
        "profit_opportunity_score": 4.0,
        "market_size_score": 8.0,
        "resellability_score": 7.0,
        "liquidity_score": 8.0,
        "risk_score": 3.0,
        "market_growth_direction": "Stable",
        "requirements": {"cpu_min_tier": "i5", "ram_min_gb": 8, "gpu_required": False, "psu_required": True},
        "search_strategy": {
            "keywords": ["student pc", "office pc no gpu", "HP EliteDesk i5", "Dell OptiPlex i5", "cheap desktop pc"],
            "price_min": 30, "price_max": 110, "listing_types": ["buy_it_now", "auction"],
        },
        "profit_strategy": {
            "target_profit_gbp": 75, "target_margin_pct": 55,
            "sell_platform": "eBay + Facebook Marketplace",
            "flip_structure": "buy_upgrade_sell",
            "notes": "Clean up, add SSD if HDD-only, Windows 11 fresh install. Target £200-260 sell price. Peak: August-September (results day + freshers week).",
        },
        "ideal_build": {
            "cpu": {
                "candidate_models": ["i5-9400", "i5-8500", "i5-10400"],
                "search_terms": ["i5 office desktop", "dell optiplex i5 9th gen", "hp elitedesk i5"],
                "negative_search_terms": ["faulty", "no power"],
            },
            "ram": {
                "candidate_models": ["16 GB DDR4", "8 GB DDR4 (upgrade to 16)"],
                "search_terms": ["16gb ddr4", "8gb ddr4"],
                "negative_search_terms": [],
            },
            "storage": {
                "candidate_models": ["500 GB SSD SATA", "1 TB NVMe SSD"],
                "search_terms": ["500gb ssd", "1tb nvme m.2"],
                "negative_search_terms": [],
            },
        },
        "seasonality": {
            "jan": 3, "feb": 4, "mar": 5, "apr": 5, "may": 6, "jun": 6,
            "jul": 7, "aug": 10, "sep": 9, "oct": 7, "nov": 6, "dec": 5,
            "peak_months": ["august", "september"], "slow_months": ["january", "february"],
            "current_position": "approaching_peak", "days_until_peak": 60,
        },
        "pricing_model": {}, "profit_model": {},
        "upgrade_strategy": {}, "upsell_strategy": {}, "component_catalogue": {},
    },

    # ── 10. Family PC ────────────────────────────────────────────────────────
    {
        "name": "Family PC",
        "emoji": "🏠",
        "status": "active",
        "target_use_case": "office",
        "target_customer": "Families with kids, parents replacing old desktops",
        "what_they_use_it_for": "Homework, YouTube, family Zoom, light gaming (Roblox / Minecraft), printing",
        "what_they_want_from_build": "Just works for everyone, fast to boot, looks clean, reliable brand name",
        "critical_success_factors": ["Reliable brand (Dell/HP/Lenovo)", "SSD fast boot", "32 GB DDR4", "Windows 11 Home", "Price under £400"],
        "profit_opportunity_score": 4.0,
        "market_size_score": 9.0,
        "resellability_score": 8.0,
        "liquidity_score": 8.0,
        "risk_score": 2.0,
        "market_growth_direction": "Stable",
        "requirements": {"cpu_min_tier": "i5", "ram_min_gb": 16, "gpu_required": False, "psu_required": True},
        "search_strategy": {
            "keywords": ["family desktop pc", "ryzen 5 desktop", "hp desktop i5", "dell desktop ryzen", "mid range desktop"],
            "price_min": 80, "price_max": 220, "listing_types": ["buy_it_now", "auction"],
        },
        "profit_strategy": {
            "target_profit_gbp": 70, "target_margin_pct": 30,
            "sell_platform": "eBay + Facebook Marketplace",
            "flip_structure": "buy_upgrade_sell",
            "notes": "Brand name matters to family buyers. Add RAM and SSD. Fresh Windows. Low risk, moderate profit. Volume play.",
        },
        "ideal_build": {
            "cpu": {
                "candidate_models": ["Ryzen 5 5600", "i5-11400", "i5-10400", "i5-12400"],
                "search_terms": ["ryzen 5 5600 desktop", "i5 11400 desktop", "mid range pc"],
                "negative_search_terms": ["faulty", "no power"],
            },
            "ram": {
                "candidate_models": ["16 GB DDR4", "32 GB DDR4"],
                "search_terms": ["16gb ddr4", "32gb ddr4"],
                "negative_search_terms": [],
            },
            "storage": {
                "candidate_models": ["1 TB NVMe SSD", "500 GB SSD SATA"],
                "search_terms": ["1tb nvme m.2", "500gb ssd sata"],
                "negative_search_terms": [],
            },
        },
        "seasonality": {
            "jan": 5, "feb": 4, "mar": 5, "apr": 5, "may": 5, "jun": 5,
            "jul": 6, "aug": 7, "sep": 7, "oct": 7, "nov": 9, "dec": 10,
            "peak_months": ["november", "december"], "slow_months": ["february"],
            "current_position": "mid_season", "days_until_peak": 155,
        },
        "pricing_model": {}, "profit_model": {},
        "upgrade_strategy": {}, "upsell_strategy": {}, "component_catalogue": {},
    },

    # ── 11. Gift-from-parents PC ─────────────────────────────────────────────
    {
        "name": "Gift-from-parents PC",
        "emoji": "🎁",
        "status": "active",
        "target_use_case": "gaming",
        "target_customer": "Parents buying a gaming PC for their teenager / young adult",
        "what_they_use_it_for": "Gaming, streaming, social media — whatever their kid told them to get",
        "what_they_want_from_build": "Looks impressive, has a good GPU (RTX 4060 — recent gen), RGB preferred, under £700",
        "critical_success_factors": ["RTX 4060 (current-gen, parents understand the number)", "RGB / good aesthetics", "Ryzen 5 / i5-12th", "32 GB DDR4", "1 TB NVMe"],
        "profit_opportunity_score": 4.0,
        "market_size_score": 7.0,
        "resellability_score": 8.0,
        "liquidity_score": 7.0,
        "risk_score": 4.0,
        "market_growth_direction": "Growing",
        "requirements": {"cpu_min_tier": "i5", "ram_min_gb": 16, "gpu_required": True, "psu_required": True},
        "search_strategy": {
            "keywords": ["rtx 4060 gaming pc", "gaming pc gift", "rtx 4060 desktop", "gaming pc i5 12th"],
            "price_min": 150, "price_max": 400, "listing_types": ["buy_it_now", "auction"],
        },
        "profit_strategy": {
            "target_profit_gbp": 100, "target_margin_pct": 22,
            "sell_platform": "eBay", "flip_structure": "buy_upgrade_sell",
            "notes": "Presentation matters — parents judge by looks and model number. RTX 4060 (not 3060) is a meaningful upgrade for this market. Good photos and clear description drive price.",
        },
        "ideal_build": {
            "cpu": {
                "candidate_models": ["i5-12400F", "i5-12600K", "Ryzen 5 5600", "Ryzen 5 7600"],
                "search_terms": ["i5 12400 gaming pc no gpu", "ryzen 5 5600 desktop no gpu"],
                "negative_search_terms": ["faulty", "for parts"],
            },
            "gpu": {
                "candidate_models": ["RTX 4060 8GB", "RTX 4060 Ti 8GB"],
                "search_terms": ["rtx 4060 8gb", "rtx 4060 ti"],
                "negative_search_terms": ["faulty", "mining"],
            },
            "ram": {
                "candidate_models": ["32 GB DDR4 3200 MHz", "16 GB DDR4 3600 MHz"],
                "search_terms": ["32gb ddr4", "16gb ddr4 3600"],
                "negative_search_terms": [],
            },
            "storage": {
                "candidate_models": ["1 TB NVMe SSD"],
                "search_terms": ["1tb nvme m.2"],
                "negative_search_terms": [],
            },
            "case": {
                "candidate_models": ["Mid-tower RGB ATX case"],
                "search_terms": ["rgb gaming case mid tower", "atx rgb case"],
                "negative_search_terms": ["damaged", "cracked"],
            },
            "psu": {
                "candidate_models": ["650 W 80+ Bronze", "750 W 80+ Gold"],
                "search_terms": ["650w psu", "750w gold psu"],
                "negative_search_terms": ["faulty"],
            },
        },
        "seasonality": {
            "jan": 3, "feb": 3, "mar": 3, "apr": 4, "may": 4, "jun": 5,
            "jul": 5, "aug": 6, "sep": 6, "oct": 7, "nov": 9, "dec": 10,
            "peak_months": ["november", "december"], "slow_months": ["january", "february", "march"],
            "current_position": "approaching_peak", "days_until_peak": 155,
        },
        "pricing_model": {}, "profit_model": {},
        "upgrade_strategy": {}, "upsell_strategy": {}, "component_catalogue": {},
    },
]

# Fixed Curated Builds. Each customer journey type maps to its own stable,
# sellable playbook/SKU instead of collapsing distinct buyers into one product.
_CURATED_RENAMES = {
    "Budget Gamer": "Great-value Gaming",
    "High-end Gamer": "High-performance Gaming",
    "Student Build": "Student Hybrid",
    "Office Station Flip": "Business & Office",
    "Content Creator": "Content Creation",
    "AI Workstation": "AI Workstation",
    "Dev Workstation": "Software Development",
    "Family PC": "Family & Home",
}
_CURATED_NAMES = set(_CURATED_RENAMES.values())

# Customer-facing names from the previous five-build catalogue. Renaming these
# rows in place preserves their IDs, slots, variants, drafts and order history.
_PREVIOUS_CURATED_RENAMES = {
    "Work & Study": "Student Hybrid",
    "Creation & Development": "Content Creation",
}


def _curated_seed_data() -> list[dict]:
    by_name = {data["name"]: data for data in _INITIAL_PLAYBOOKS}
    curated: list[dict] = []
    for source_name, curated_name in _CURATED_RENAMES.items():
        data = dict(by_name[source_name])
        data["name"] = curated_name
        if curated_name == "Student Hybrid":
            data.update({
                "target_customer": "Students who need one affordable machine for coursework and gaming",
                "what_they_use_it_for": "Study, coding, video calls, research, media and 1080p gaming",
                "what_they_want_from_build": "Strong everyday responsiveness and credible gaming performance on a student budget",
            })
        elif curated_name == "Content Creation":
            data.update({
                "target_customer": "Video editors, streamers, photographers, designers and 3D artists",
                "what_they_use_it_for": "Editing, rendering, streaming, photography, design and animation",
                "what_they_want_from_build": "Strong multi-core and GPU performance with fast expandable storage",
            })
        curated.append(data)
    return curated


_CURATED_PLAYBOOKS = _curated_seed_data()

# Playbooks that existed in previous versions and are now retired
_RETIRE_NAMES = {
    # v2 playbooks being replaced
    "Mainstream Gamer",
    "RGB Showcase Build",
    "Competitive Gaming Build",
    "Premium Showcase",
    # v1 inline-seeded playbooks from main.py
    "Budget Gaming PC",
    "Office Workstation Flip",
    "AI / ML Workstation",
    "Budget Builder (Sub-£100)",
    # Playbooks created by AI proposal/evolution engine — now superseded
    "Software Engineer Workstation",
    "High-End Gaming PC",
    "Mid-Range Gaming PC",
}

# Old name → new name renames to apply if the old record exists
_RENAMES = {
    "Developer Workstation": "Dev Workstation",
    "Ultra Budget Flip":     "Ultra-Budget Flip",
}


async def refresh_playbook_economics_from_benchmarks() -> int:
    """
    Standalone helper — creates its own DB session, loads fresh benchmarks,
    and updates pricing_model/profit_model on every active playbook.
    Called by run_price_refresh() after the nightly eBay scrape completes.
    Returns the number of playbooks updated.
    """
    import structlog
    from app.database import AsyncSessionLocal
    from app.services.price_refresh import load_benchmarks
    from sqlalchemy import select as sa_select

    log = structlog.get_logger(__name__)
    benchmarks = load_benchmarks()
    if not benchmarks:
        log.warning("playbook_economics.no_benchmarks_skipping")
        return 0

    updated = 0
    async with AsyncSessionLocal() as db:
        result = await db.execute(sa_select(Playbook).where(Playbook.status == "active"))
        playbooks = result.scalars().all()
        for pb in playbooks:
            economics = compute_live_economics(pb.name, benchmarks)
            if economics:
                pb.pricing_model = economics.get("pricing_model", pb.pricing_model)
                pb.profit_model  = economics.get("profit_model",  pb.profit_model)
                updated += 1
        await db.commit()

    log.info("playbook_economics.refreshed", updated=updated)
    return updated


async def seed_playbooks(db: AsyncSession) -> int:
    """
    Idempotent playbook migration:
    1. Rename retained strategies to their customer-facing product names
    2. Deprecate every other strategy (never delete: preserve foreign keys)
    3. Insert any missing curated playbooks
    4. Refresh pricing_model / profit_model on every curated playbook

    Returns total playbooks created.
    """
    from datetime import datetime as dt
    from app.services.price_refresh import load_benchmarks

    benchmarks = load_benchmarks()

    # ── Step 0: preserve existing IDs, slots and variants by renaming rows.
    for source_name, curated_name in _PREVIOUS_CURATED_RENAMES.items():
        source_result = await db.execute(select(Playbook).where(Playbook.name == source_name))
        source = source_result.scalar_one_or_none()
        target_result = await db.execute(select(Playbook).where(Playbook.name == curated_name))
        target = target_result.scalar_one_or_none()
        if source and target is None:
            source.name = curated_name
            source.status = PlaybookStatus.ACTIVE
        elif source and target is not None:
            source.status = PlaybookStatus.DEPRECATED

    for source_name, curated_name in _CURATED_RENAMES.items():
        if source_name == curated_name:
            continue
        source_result = await db.execute(select(Playbook).where(Playbook.name == source_name))
        source = source_result.scalar_one_or_none()
        target_result = await db.execute(select(Playbook).where(Playbook.name == curated_name))
        target = target_result.scalar_one_or_none()
        if source and target is None:
            source.name = curated_name
            source.status = PlaybookStatus.ACTIVE
        elif source and target is not None:
            source.status = PlaybookStatus.DEPRECATED

    # Keep the internal and external catalogue identical: only the five
    # Curated Builds remain active.
    active_result = await db.execute(select(Playbook).where(Playbook.status == "active"))
    for playbook in active_result.scalars().all():
        if playbook.name not in _CURATED_NAMES:
            playbook.status = PlaybookStatus.DEPRECATED

    # ── Step 1: retire removed playbooks ─────────────────────────────────────
    for retired_name in _RETIRE_NAMES:
        r = await db.execute(select(Playbook).where(Playbook.name == retired_name))
        pb = r.scalar_one_or_none()
        if pb and pb.status != "deprecated":
            pb.status = "deprecated"

    # ── Step 2: rename where applicable ──────────────────────────────────────
    for old_name, new_name in _RENAMES.items():
        r = await db.execute(select(Playbook).where(Playbook.name == old_name))
        pb = r.scalar_one_or_none()
        if pb:
            # Only rename if the new name doesn't already exist
            r2 = await db.execute(select(Playbook).where(Playbook.name == new_name))
            if r2.scalar_one_or_none() is None:
                pb.name = new_name

    # ── Step 3 + 4: insert missing, update pricing on all active ones ─────────
    created = 0
    for data in _CURATED_PLAYBOOKS:
        economics = compute_live_economics(data["name"], benchmarks)

        r = await db.execute(select(Playbook).where(Playbook.name == data["name"]))
        existing = r.scalar_one_or_none()

        if existing is None:
            pb_data = {k: v for k, v in data.items() if k not in ("pricing_model", "profit_model")}
            pb_data.update(economics)
            if isinstance(pb_data.get("status"), str):
                pb_data["status"] = PlaybookStatus(pb_data["status"])
            pb = Playbook(**pb_data, activated_at=dt.utcnow())
            db.add(pb)
            created += 1
        else:
            # Refresh live pricing even for existing records
            if economics:
                existing.pricing_model = economics.get("pricing_model", existing.pricing_model)
                existing.profit_model  = economics.get("profit_model",  existing.profit_model)

    await db.commit()
    return created
