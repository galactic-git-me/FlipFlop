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

# What different RAM amounts add to the resale value of a complete system
RAM_ADD_RESALE: dict[int, float] = {
    4: 0, 8: 15, 16: 35, 32: 60, 64: 90,
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

BUDGET_GPU_COST        = 185   # RTX 3060 12GB used UK (£170-200 typical)
BUDGET_GPU_RESALE_ADD  = 240   # RTX 3060 customer-perceived value in a complete system

BUDGET_SSD_COST        = 65    # 1TB NVMe new Amazon UK (~£60-70)
BUDGET_SSD_RESALE_ADD  = 70    # 1TB NVMe customer value

BUDGET_PSU_COST        = 50    # 650W 80+ Bronze new (~£45-55)
BUDGET_PSU_RESALE_ADD  = 35    # modest — buyers expect a PSU, don't pay premium for it

BUDGET_CASE_COST       = 70    # Themed RGB gaming case new (Amazon/eBay £60-80)
# Case premium RULE: buyer perceives a themed case as worth 2× what we paid.
# This reflects the transformation premium — the same PC in a £70 themed case
# is meaningfully more desirable than a bare tower.
BUDGET_CASE_RESALE_ADD = 2 * BUDGET_CASE_COST   # = £140

BUDGET_RAM_COST        = 65    # 32GB DDR4-3200 kit (2×16GB used, ~£60-70)
BUDGET_RAM_RESALE_ADD  = 60    # 32GB adds meaningful value — gaming minimum is now 32GB

# AM5 platform overhead — motherboard + DDR5 RAM are required before anything else.
# These are NOT included in standard upgrade_cost because the default model assumes
# the listing already has a board and DDR4. AM5 listings need these added explicitly.
AM5_MOBO_COST  = 130   # budget B650 motherboard new (~£120-140)
AM5_DDR5_COST  = 70    # 32GB DDR5-5600 kit new (~£65-75)

# Build quality / presentation uplift — premium buyers pay for a clean, tested,
# well-presented build (good photos, cable management, etc.).
PRESENTATION_UPLIFT    = 75

PLATFORM_FEE = 0.127  # eBay ~12.7% (Final Value Fee)


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
    base = _cpu_base(cpu)

    # GPU: existing GPU lookup or RTX 3060-class upgrade contribution
    base += _gpu_add(gpu) if gpu else BUDGET_GPU_RESALE_ADD

    # RAM: finished product always has ≥ 32 GB (per flip spec).
    # If the listing already has 32 GB+ use its actual resale contribution.
    # Otherwise (anything < 32 GB, or unknown) we buy a 32 GB kit, so the
    # finished product has 32 GB and commands the 32 GB resale value.
    if ram_gb and ram_gb >= 32:
        base += RAM_ADD_RESALE.get(ram_gb, RAM_ADD_RESALE[32])
    else:
        base += BUDGET_RAM_RESALE_ADD   # finished product has 32 GB → £60

    # Storage: existing type value or 1TB NVMe upgrade
    base += _storage_add(storage_gb, storage_type) if storage_gb else BUDGET_SSD_RESALE_ADD

    # Themed case (2 × cost rule) + clean-build presentation premium
    base += BUDGET_CASE_RESALE_ADD   # = 2 × £70 = £140
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
    cost = float(BUDGET_CASE_COST)  # always buy a case
    if not gpu:
        cost += BUDGET_GPU_COST
    if not storage_gb:
        cost += BUDGET_SSD_COST
    if not has_psu:
        cost += BUDGET_PSU_COST
    if not ram_gb or ram_gb < 32:   # 32 GB is the 2026 gaming minimum
        cost += BUDGET_RAM_COST
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
    platform_fees = round(estimated_resale * PLATFORM_FEE, 2)
    total_cost    = round(buy_price + upgrade_cost + platform_fees, 2)
    return round(estimated_resale - total_cost, 2)


# ── internal helpers ──────────────────────────────────────────────────────────

def _cpu_base(cpu: str | None) -> float:
    if not cpu:
        return 55   # completely unknown machine — conservative
    cpu_lower = cpu.lower()
    for key, val in CPU_BASE_RESALE.items():
        if key in cpu_lower:
            return val
    # Tier-based fallback for unrecognised generations (e.g. future CPUs,
    # unusual model numbers).  Much better than a flat £75.
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
