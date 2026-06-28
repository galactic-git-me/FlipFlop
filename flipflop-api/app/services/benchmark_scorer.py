"""
RAM derived scoring + performance/£ calculations + opportunity scoring + gem detection.
Pure Python — no network or DB calls.
"""
from __future__ import annotations
import math
from typing import Optional

NEGATIVE_KEYWORDS = [
    "box only", "empty box", "cooler only", "fan only", "faulty",
    "broken", "untested", "for parts", "not working", "spares repair",
    "no display", "artifacting", "spares or repair",
]

_DDR_BASE = {"DDR5": 100.0, "DDR4": 60.0, "DDR3": 25.0, "DDR2": 5.0}

_CPU_MARKETABILITY = {
    "amd_ryzen_7_7800x3d": 95, "amd_ryzen_9_7950x3d": 90,
    "amd_ryzen_5_7600x": 75, "amd_ryzen_7_7700x": 80,
    "intel_core_i9_13900k": 85, "intel_core_i7_13700k": 80,
    "intel_core_i5_12400f": 70, "intel_core_i5_13400f": 72,
    "amd_ryzen_5_5600x": 72, "amd_ryzen_7_5800x3d": 88,
}
_GPU_MARKETABILITY = {
    "nvidia_geforce_rtx_4090": 95, "nvidia_geforce_rtx_4080": 90,
    "nvidia_geforce_rtx_4070_ti": 85, "nvidia_geforce_rtx_4070": 82,
    "nvidia_geforce_rtx_3090": 80, "nvidia_geforce_rtx_3080": 82,
    "nvidia_geforce_rtx_3070": 78, "nvidia_geforce_rtx_3060_ti": 75,
    "nvidia_geforce_rtx_3060": 72, "amd_radeon_rx_7900_xtx": 85,
    "amd_radeon_rx_6800_xt": 74, "amd_radeon_rx_6700_xt": 70,
}


def score_ram(
    generation: str,
    capacity_gb: float,
    speed_mts: float,
    cas_latency: float,
    dual_channel: bool = True,
    rgb: bool = False,
    xmp: bool = False,
    expo: bool = False,
) -> float:
    """Derive a comparable RAM performance score from specs (0–200 range)."""
    base = _DDR_BASE.get(generation.upper().replace(" ", ""), 40.0)
    speed_bonus = min(40.0, max(0.0, (speed_mts - 2133) / 100.0))
    lat_penalty = max(0.0, (cas_latency - 16) * 0.5)
    cap_bonus = math.log2(max(1, capacity_gb)) * 5.0
    dual_bonus = 15.0 if dual_channel else 0.0
    rgb_bonus = 5.0 if rgb else 0.0
    mem_bonus = 8.0 if (xmp or expo) else 0.0
    return round(base + speed_bonus + cap_bonus + dual_bonus + rgb_bonus + mem_bonus - lat_penalty, 1)


def calc_performance_per_pound(benchmark_score: float, price: float) -> float:
    if price <= 0:
        return 0.0
    return round(benchmark_score / price, 2)


def calc_cpu_opportunity_score(
    performance_per_pound: float,
    marketability_score: float,
    demand_score: float,
    upgradeability_score: float,
    liquidity_score: float,
    max_ppp: float = 300.0,
) -> float:
    """Weighted CPU opportunity score, 0–100."""
    ppp_norm = min(100.0, (performance_per_pound / max(max_ppp, 1)) * 100)
    raw = (
        ppp_norm * 0.30
        + marketability_score * 0.25
        + demand_score * 0.20
        + upgradeability_score * 0.15
        + liquidity_score * 0.10
    )
    return round(min(100.0, max(0.0, raw)), 1)


def calc_gpu_opportunity_score(
    performance_per_pound: float,
    marketability_score: float,
    demand_score: float,
    vram_score: float,
    liquidity_score: float,
    max_ppp: float = 250.0,
) -> float:
    """Weighted GPU opportunity score, 0–100."""
    ppp_norm = min(100.0, (performance_per_pound / max(max_ppp, 1)) * 100)
    raw = (
        ppp_norm * 0.35
        + marketability_score * 0.25
        + demand_score * 0.20
        + vram_score * 0.10
        + liquidity_score * 0.10
    )
    return round(min(100.0, max(0.0, raw)), 1)


def calc_build_opportunity_score(
    expected_profit_score: float,
    performance_value_score: float,
    demand_score: float,
    liquidity_score: float,
    marketability_score: float,
    risk_adjustment: float = 0.0,
) -> float:
    """Build-level opportunity score (0–100)."""
    raw = (
        expected_profit_score * 0.25
        + performance_value_score * 0.20
        + demand_score * 0.20
        + liquidity_score * 0.15
        + marketability_score * 0.15
        + risk_adjustment * 0.05
    )
    return round(min(100.0, max(0.0, raw)), 1)


def get_marketability(component_type: str, normalized_model: str) -> float:
    if component_type == "cpu":
        return float(_CPU_MARKETABILITY.get(normalized_model, 50))
    if component_type == "gpu":
        return float(_GPU_MARKETABILITY.get(normalized_model, 50))
    return 50.0


def is_gem_candidate(
    component_price: float,
    avg_sold_price: float,
    performance_per_pound: float,
    category_avg_ppp: float,
    price_threshold: float = 0.80,
    ppp_threshold: float = 1.25,
) -> bool:
    """True when the component is both cheap vs market AND performant vs category average."""
    if avg_sold_price <= 0 or category_avg_ppp <= 0:
        return False
    price_ok = component_price <= avg_sold_price * price_threshold
    ppp_ok = performance_per_pound >= category_avg_ppp * ppp_threshold
    return price_ok and ppp_ok


def has_negative_keyword(text: str) -> bool:
    t = text.lower()
    return any(kw in t for kw in NEGATIVE_KEYWORDS)


def calc_risk_adjustment(
    seller_suspicious: bool = False,
    price_too_low: bool = False,
    untested: bool = False,
    faulty: bool = False,
    no_photos: bool = False,
) -> float:
    """Return 0–100 risk score (higher = riskier)."""
    score = 0.0
    if seller_suspicious: score += 25
    if price_too_low:     score += 20
    if untested:          score += 20
    if faulty:            score += 30
    if no_photos:         score += 15
    return min(100.0, score)
