"""
Estimation Engine — calculates AFTER-UPGRADE resale value and profit.

The "resale" figure is what the FULLY FINISHED themed PC sells for on eBay:
  - CPU base value
  + GPU upgrade (budget RX 580 if none present)
  + RAM contribution
  + Storage upgrade (budget SSD if none present)
  + Themed case (always added — this is what makes it a flip product)

The "upgrade cost" is the total cash you spend to get it there:
  - GPU (£65 if missing)
  - SSD (£28 if missing)
  - PSU (£30 if missing)
  - Themed case (£35 always — sourced from Temu / AliExpress)

profit = after_upgrade_resale - buy_price - upgrade_cost - platform_fees
"""

# Base resale values by CPU generation (complete machine, no GPU, clean install)
CPU_BASE_RESALE: dict[str, float] = {
    # Intel — 4th gen
    "i3-4": 55,  "i5-4": 80,  "i7-4": 95,
    # Intel — 5th gen (uncommon)
    "i5-5": 90,  "i7-5": 120,
    # Intel — 6th gen
    "i3-6": 70,  "i5-6": 105, "i7-6": 135,
    # Intel — 7th gen
    "i3-7": 75,  "i5-7": 115, "i7-7": 150,
    # Intel — 8th gen
    "i3-8": 85,  "i5-8": 135, "i7-8": 175,
    # Intel — 9th gen
    "i3-9": 95,  "i5-9": 155, "i7-9": 195, "i9-9": 255,
    # Intel — 10th gen
    "i3-10": 100, "i5-10": 165, "i7-10": 215, "i9-10": 265,
    # Intel — 11th gen
    "i3-11": 110, "i5-11": 175, "i7-11": 235, "i9-11": 285,
    # Intel — 12th gen
    "i3-12": 135, "i5-12": 215, "i7-12": 295, "i9-12": 365,
    # Intel — 13th gen
    "i3-13": 145, "i5-13": 245, "i7-13": 335, "i9-13": 425,
    # Intel — 14th gen
    "i5-14": 255, "i7-14": 355, "i9-14": 445,
    # AMD Ryzen 3000 — including Ryzen 9 (3900X is a 12-core flagship)
    "ryzen 3 3": 125, "ryzen 5 3": 155, "ryzen 7 3": 205, "ryzen 9 3": 260,
    # AMD Ryzen 5000
    "ryzen 3 5": 145, "ryzen 5 5": 195, "ryzen 7 5": 275, "ryzen 9 5": 355,
    # AMD Ryzen 7000
    "ryzen 5 7": 245, "ryzen 7 7": 335, "ryzen 9 7": 435,
    # Xeon
    "xeon e3": 115, "xeon e5": 155, "xeon w": 195,
}

# What each GPU adds to the RESALE VALUE of a complete themed PC
# (i.e. what the buyer perceives/pays for, not what the GPU costs us)
# Prices reflect current UK eBay/Amazon market — updated 2025/26
GPU_ADD_RESALE: dict[str, float] = {
    # GTX 10-series
    "gtx 1050": 50,      "gtx 1050 ti": 70,
    "gtx 1060 3gb": 80,  "gtx 1060 6gb": 105,
    "gtx 1070": 130,     "gtx 1070 ti": 160,
    "gtx 1080": 190,     "gtx 1080 ti": 240,
    # GTX 16-series
    "gtx 1650": 80,      "gtx 1650 super": 100,
    "gtx 1660": 115,     "gtx 1660 super": 140, "gtx 1660 ti": 145,
    # RTX 20-series
    "rtx 2060": 170,     "rtx 2070": 220,  "rtx 2080": 285,
    # RTX 30-series
    "rtx 3060": 240,     "rtx 3070": 330,  "rtx 3080": 440,
    # RTX 40-series
    "rtx 4060": 290,     "rtx 4070": 420,  "rtx 4080": 580,
    # AMD RX 5xx
    "rx 580": 90,        "rx 590": 110,
    # AMD RX 5xxx
    "rx 5600": 115,      "rx 5700": 175,   "rx 5700 xt": 215,
    # AMD RX 6xxx
    "rx 6600": 200,      "rx 6650": 220,
    "rx 6700": 265,      "rx 6750": 285,
    "rx 6800": 345,      "rx 6900": 420,
    # AMD RX 7xxx
    "rx 7600": 245,      "rx 7700": 310,   "rx 7800": 380,
}

# What different RAM amounts add to the resale value of a complete system.
# Updated June 2026: DDR4 prices have surged ~2-3× due to AI supply crunch.
# 32GB is now the buyer expectation for a gaming PC; 64GB commands a premium.
RAM_ADD_RESALE: dict[int, float] = {
    4: 0, 8: 15, 16: 50, 32: 110, 64: 160,
}

# What storage adds to resale value (customer perception of included storage)
STORAGE_ADD_RESALE: dict[str, float] = {
    "none": 0, "hdd": 15, "ssd": 55, "nvme": 75,
}

# ── Budget upgrade components ─────────────────────────────────────────────────
#
# TWO numbers per component:
#   RESALE ADD = value to the customer / contribution to selling price
#   COST       = what WE actually pay to buy it
#
# GPU: RTX 3060 12GB is the primary upgrade target (per flip spec).
#      RTX 2060 is the budget fallback.
# RAM: 32GB DDR4 minimum (2×16GB kit) — 64GB ideal.
# SSD: 1TB NVMe (standard gaming minimum 2025/26).
# Case: themed RGB, £60-80 to buy.  RESALE ADD = 2 × cost (per flip spec rule).
# Presentation uplift: premium for a clean, tested, well-photographed build.


# ── Budget component costs ────────────────────────────────────────────────────
#
# These are FALLBACK constants used only when data/price_benchmarks.json is
# missing or older than 48 hours. Under normal operation the daily price_refresh
# job writes live eBay UK sold prices to that file and get_budget_costs() reads
# from it, keeping all profit calculations current.
#
# Last manually reviewed: June 2026. DDR4/DDR5 prices are in a supply crisis
# (AI datacenter demand + production cuts). Update here if price_refresh breaks.

_BUDGET_GPU_COST_DEFAULT       = 220   # RTX 3060 12GB used UK (£200-250 in June 2026)
_BUDGET_GPU_RESALE_ADD_DEFAULT = 260   # RTX 3060 contribution to completed PC resale

_BUDGET_SSD_COST_DEFAULT       = 60    # 1TB NVMe new Amazon UK (~£55-65)
_BUDGET_SSD_RESALE_ADD_DEFAULT = 70    # 1TB NVMe customer value

_BUDGET_PSU_COST_DEFAULT       = 50    # 650W 80+ Bronze new (~£45-55)
_BUDGET_PSU_RESALE_ADD_DEFAULT = 35

_BUDGET_CASE_COST_DEFAULT      = 70    # Themed RGB gaming case (Amazon/eBay £60-80)
_BUDGET_CASE_RESALE_ADD_DEFAULT = 2 * _BUDGET_CASE_COST_DEFAULT   # = £140

_BUDGET_RAM_COST_DEFAULT       = 130   # 32GB DDR4 kit used UK (£100-160 in June 2026;
                                        # DDR4 in supply crisis — was £65 in 2024)
_BUDGET_RAM_RESALE_ADD_DEFAULT = 110   # 32GB DDR4 adds ~£110 to a completed PC in 2026


def get_budget_costs() -> dict[str, float]:
    """
    Return current budget-component costs and resale values.

    Tries data/price_benchmarks.json (written by the daily price_refresh job)
    first. Falls back to hardcoded defaults if the file is missing or stale.
    Keys in price_benchmarks.json match the BUDGET_COMPONENT_QUERIES names in
    price_refresh.py (e.g. "cost_gpu_rtx3060", "cost_ram_32gb_ddr4").
    """
    try:
        from app.services.price_refresh import load_benchmarks
        b = load_benchmarks()
    except Exception:
        b = {}

    gpu_cost = b.get("cost_gpu_rtx3060", _BUDGET_GPU_COST_DEFAULT)
    ram_cost = b.get("cost_ram_32gb_ddr4", _BUDGET_RAM_COST_DEFAULT)

    return {
        "gpu_cost":        gpu_cost,
        "gpu_resale_add":  round(gpu_cost * 1.15, 2) if b.get("cost_gpu_rtx3060") else _BUDGET_GPU_RESALE_ADD_DEFAULT,
        "ssd_cost":        b.get("cost_ssd_1tb_nvme",  _BUDGET_SSD_COST_DEFAULT),
        "ssd_resale_add":  _BUDGET_SSD_RESALE_ADD_DEFAULT,
        "psu_cost":        b.get("cost_psu_650w",      _BUDGET_PSU_COST_DEFAULT),
        "psu_resale_add":  _BUDGET_PSU_RESALE_ADD_DEFAULT,
        "case_cost":       b.get("cost_case_rgb",      _BUDGET_CASE_COST_DEFAULT),
        "case_resale_add": round(b.get("cost_case_rgb", _BUDGET_CASE_COST_DEFAULT) * 2, 2),
        "ram_cost":        ram_cost,
        "ram_resale_add":  round(ram_cost * 0.85, 2) if b.get("cost_ram_32gb_ddr4") else _BUDGET_RAM_RESALE_ADD_DEFAULT,
    }


# Module-level shims so existing imports of BUDGET_* still work.
# These read from the live benchmarks at call time — not at import time.
# Any code that does `from estimator import BUDGET_RAM_COST` will get the
# stale constant; prefer calling get_budget_costs() directly instead.
BUDGET_GPU_COST        = _BUDGET_GPU_COST_DEFAULT
BUDGET_GPU_RESALE_ADD  = _BUDGET_GPU_RESALE_ADD_DEFAULT
BUDGET_SSD_COST        = _BUDGET_SSD_COST_DEFAULT
BUDGET_SSD_RESALE_ADD  = _BUDGET_SSD_RESALE_ADD_DEFAULT
BUDGET_PSU_COST        = _BUDGET_PSU_COST_DEFAULT
BUDGET_PSU_RESALE_ADD  = _BUDGET_PSU_RESALE_ADD_DEFAULT
BUDGET_CASE_COST       = _BUDGET_CASE_COST_DEFAULT
BUDGET_CASE_RESALE_ADD = _BUDGET_CASE_RESALE_ADD_DEFAULT
BUDGET_RAM_COST        = _BUDGET_RAM_COST_DEFAULT
BUDGET_RAM_RESALE_ADD  = _BUDGET_RAM_RESALE_ADD_DEFAULT

# AM5 platform overhead — motherboard + DDR5 RAM are required before anything else.
# These are NOT included in standard upgrade_cost because the default model assumes
# the listing already has a board and DDR4. AM5 listings need these added explicitly.
AM5_MOBO_COST  = 130   # budget B650 motherboard new (~£120-140)
AM5_DDR5_COST  = 70    # 32GB DDR5-5600 kit new (~£65-75)

# Build quality / presentation uplift — premium buyers pay for a clean, tested,
# well-presented build (good photos, cable management, etc.).
PRESENTATION_UPLIFT    = 75

def _platform_fee() -> float:
    """Live fee rate — override via EBAY_FINAL_VALUE_FEE_PCT env var (e.g. 0.0 when eBay runs a free-fees promo)."""
    from app.config import get_settings
    return get_settings().ebay_final_value_fee_pct

PLATFORM_FEE = 0.127  # kept for imports that reference this directly; use _platform_fee() for live rate


def estimate_resale(
    cpu: str | None,
    ram_gb: int | None,
    ram_type: str | None,
    storage_gb: int | None,
    storage_type: str | None,
    gpu: str | None,
) -> float:
    """
    Returns the estimated AFTER-UPGRADE selling price of the fully finished,
    themed build — what it would fetch on eBay.

    Structure (mirrors the waterfall model):
      CPU base value
      + GPU resale contribution  (existing GPU or RTX 3060 we add)
      + RAM resale contribution  (existing or 32GB we add)
      + Storage resale           (existing or 1TB NVMe we add)
      + Case premium             (= 2 × case cost, per flip spec rule)
      + Presentation uplift      (clean tested build premium)
    """
    bc = get_budget_costs()
    base = _cpu_base(cpu)

    # GPU: existing GPU lookup or RTX 3060-class upgrade contribution
    base += _gpu_add(gpu) if gpu else bc["gpu_resale_add"]

    # RAM: finished product always has ≥ 32 GB (per flip spec).
    # If the listing already has 32 GB+ use its actual resale contribution.
    # Otherwise (anything < 32 GB, or unknown) we buy a 32 GB kit, so the
    # finished product has 32 GB and commands the 32 GB resale value.
    if ram_gb and ram_gb >= 32:
        base += RAM_ADD_RESALE.get(ram_gb, bc["ram_resale_add"])
    else:
        base += bc["ram_resale_add"]

    # Storage: existing type value or 1TB NVMe upgrade
    base += _storage_add(storage_gb, storage_type) if storage_gb else bc["ssd_resale_add"]

    # Themed case (2 × cost rule) + clean-build presentation premium
    base += bc["case_resale_add"]
    base += PRESENTATION_UPLIFT      # = £75

    return round(base, 2)


def estimate_upgrade_cost(
    storage_gb: int | None,
    gpu: str | None,
    has_psu: bool,
    ram_gb: int | None = None,
    is_am5: bool = False,
) -> float:
    """
    Actual cash spend to make the listing a finished themed product.
    Always includes a themed case — it is a required part of every flip.
    """
    bc = get_budget_costs()
    cost = float(bc["case_cost"])   # always buy a case
    if not gpu:
        cost += bc["gpu_cost"]
    if not storage_gb:
        cost += bc["ssd_cost"]
    if not has_psu:
        cost += bc["psu_cost"]
    if not ram_gb or ram_gb < 32:   # 32 GB is the 2026 gaming minimum
        cost += bc["ram_cost"]
    if is_am5:
        # AM5 needs a new motherboard and DDR5 kit — not in the standard model
        cost += AM5_MOBO_COST + AM5_DDR5_COST
    return cost


def estimate_profit(
    buy_price: float,
    estimated_resale: float,   # the AFTER-UPGRADE resale from estimate_resale()
    upgrade_cost: float = 0.0,
) -> float:
    """
    Single-formula profit calculation.

    ALL costs are aggregated first, then subtracted from resale:
        total_cost = buy_price + upgrade_cost + platform_fees
        profit     = estimated_resale - total_cost

    Value adds (GPU, RAM, SSD, case, presentation) are baked into
    estimated_resale — they are NOT profit and must NOT be added here.
    """
    platform_fees = round(estimated_resale * _platform_fee(), 2)
    total_cost    = round(buy_price + upgrade_cost + platform_fees, 2)
    return round(estimated_resale - total_cost, 2)


# ── benchmark key maps ────────────────────────────────────────────────────────
# Map estimator lookup strings → price_benchmarks.json keys (from price_refresh.py)

# GPU: benchmark key → contribution when installed in a complete PC (90% of standalone)
_GPU_BENCH_KEYS: dict[str, str] = {
    "gtx 1060 6gb":  "gpu_gtx1060_6gb",
    "gtx 1070":      "gpu_gtx1070",
    "gtx 1080":      "gpu_gtx1080",
    "gtx 1080 ti":   "gpu_gtx1080ti",
    "gtx 1660 super":"gpu_gtx1660super",
    "gtx 1660 ti":   "gpu_gtx1660ti",
    "rtx 2060":      "gpu_rtx2060",
    "rtx 2070":      "gpu_rtx2070",
    "rtx 2080":      "gpu_rtx2080",
    "rtx 3060 ti":   "gpu_rtx3060ti",   # must come before "rtx 3060"
    "rtx 3060":      "gpu_rtx3060",
    "rtx 3070":      "gpu_rtx3070",
    "rtx 3080":      "gpu_rtx3080",
    "rtx 3090":      "gpu_rtx3090",
    "rtx 4060 ti":   "gpu_rtx4060ti",   # before "rtx 4060"
    "rtx 4060":      "gpu_rtx4060",
    "rtx 4070 super":"gpu_rtx4070super",
    "rtx 4070":      "gpu_rtx4070",
    "rtx 4080":      "gpu_rtx4080",
    "rx 580":        "gpu_rx580",
    "rx 5700 xt":    "gpu_rx5700xt",
    "rx 6600 xt":    "gpu_rx6600xt",    # before "rx 6600"
    "rx 6600":       "gpu_rx6600",
    "rx 6700 xt":    "gpu_rx6700xt",
    "rx 6750 xt":    "gpu_rx6750xt",
    "rx 6800 xt":    "gpu_rx6800xt",    # before "rx 6800"
    "rx 6800":       "gpu_rx6800",
    "rx 6900 xt":    "gpu_rx6900xt",
    "rx 7600":       "gpu_rx7600",
    "rx 7700 xt":    "gpu_rx7700xt",
    "rx 7800 xt":    "gpu_rx7800xt",
    "rx 7900 xtx":   "gpu_rx7900xtx",  # before "rx 7900 xt"
    "rx 7900 xt":    "gpu_rx7900xt",
}

# CPU: CPU_BASE_RESALE key → system price benchmark key
_CPU_BENCH_KEYS: dict[str, str] = {
    "i5-8": "sys_i5_8",   "i7-8": "sys_i7_8",
    "i5-9": "sys_i5_9",   "i7-9": "sys_i7_9",   "i9-9": "sys_i9_9",
    "i5-10": "sys_i5_10", "i7-10": "sys_i7_10",
    "i5-12": "sys_i5_12", "i7-12": "sys_i7_12",
    "i5-13": "sys_i5_13", "i7-13": "sys_i7_13",
    "i5-14": "sys_i5_14", "i7-14": "sys_i7_14",
    "ryzen 5 3": "sys_r5_3600", "ryzen 7 3": "sys_r7_3700", "ryzen 9 3": "sys_r9_3900",
    "ryzen 5 5": "sys_r5_5600", "ryzen 7 5": "sys_r7_5800", "ryzen 9 5": "sys_r9_5900",
    # AM5 (Ryzen 7000 / 9000)
    "ryzen 5 7": "sys_r5_7600", "ryzen 7 7": "sys_r7_7700",
    "ryzen 9 7": "sys_r9_7900",
    "ryzen 5 9": "sys_r5_9600", "ryzen 7 9": "sys_r7_9700",
}


def _benchmarks() -> dict[str, float]:
    """Single call point — cached per-process via price_refresh's module globals."""
    try:
        from app.services.price_refresh import load_benchmarks
        return load_benchmarks()
    except Exception:
        return {}


# ── internal helpers ──────────────────────────────────────────────────────────

def _cpu_base(cpu: str | None) -> float:
    if not cpu:
        return 55   # completely unknown machine — conservative
    cpu_lower = cpu.lower()
    b = _benchmarks()

    # Check live benchmark keys first (daily eBay UK sold medians)
    for table_key, bench_key in _CPU_BENCH_KEYS.items():
        if table_key in cpu_lower and bench_key in b:
            return b[bench_key]

    # Fall back to static table
    for key, val in CPU_BASE_RESALE.items():
        if key in cpu_lower:
            return val

    # Tier-based fallback for unrecognised generations
    if "ryzen 9"        in cpu_lower: return 260
    if "ryzen 7"        in cpu_lower: return 195
    if "ryzen 5"        in cpu_lower: return 155
    if "ryzen 3"        in cpu_lower: return 115
    if "i9"             in cpu_lower: return 280
    if "i7"             in cpu_lower: return 175
    if "i5"             in cpu_lower: return 135
    if "i3"             in cpu_lower: return 90
    if "xeon"           in cpu_lower: return 145
    if "threadripper"   in cpu_lower: return 350
    return 80   # absolute unknown


def _gpu_add(gpu: str | None) -> float:
    if not gpu:
        return 0
    gpu_lower = gpu.lower()
    b = _benchmarks()

    # Live benchmark: standalone eBay sold price × 0.90 = in-system contribution
    # (buyers pay ~10% less for a GPU inside a PC than buying it standalone)
    for label, bench_key in _GPU_BENCH_KEYS.items():
        if label in gpu_lower and bench_key in b:
            return round(b[bench_key] * 0.90, 2)

    # Fall back to static table
    for key, val in GPU_ADD_RESALE.items():
        if key in gpu_lower:
            return val

    return 28   # unrecognised GPU — a little value


def _storage_add(storage_gb: int | None, storage_type: str | None) -> float:
    if not storage_gb:
        return 0
    t = (storage_type or "ssd").lower()
    if "nvme" in t or "m.2" in t:
        return STORAGE_ADD_RESALE["nvme"]
    if "ssd" in t:
        return STORAGE_ADD_RESALE["ssd"]
    return STORAGE_ADD_RESALE["hdd"]  # spinning rust — still some value
