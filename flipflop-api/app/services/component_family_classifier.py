"""Classifies a component listing title into a reusable 3D-asset "family"
bucket — the strategy agreed 2026-08-13: model each visually-distinct
family ONCE (e.g. "ASUS ATX motherboard", "large triple-fan GPU") and reuse
that model across every catalogue variant in that bucket, instead of
generating one model per SKU or even one model per whole category.

Conservative by design: candidate listings for a slot can include complete
desktop listings alongside bare components — a scraped listing with
populated cpu/ram_gb fields matches the seeding query either way (see e.g.
"HP EliteDesk 800 G2 SFF – i5-6500 / 32GB RAM – No Storage" showing up as a
"cpu" slot candidate). A wrong bucket guess would show the customer a
materially wrong-looking part, which is worse than falling back to the
existing plain category-generic placeholder. Every classify_* function
returns None rather than a low-confidence guess — same principle as
_infer_cpu_socket etc. in compatibility_engine.py.

Where a category doesn't need bucketing at all (storage and OS — mostly
concealed / low visual variance), there's no classify_* function; callers
just get None and use the plain per-category generic.
"""
from __future__ import annotations

import re


def _norm(text: str) -> str:
    return (text or "").lower()


# ---- CPU: brand only — concealed under the cooler in practice -------------
def _classify_cpu(title: str) -> str | None:
    t = _norm(title)
    if re.search(r"\bryzen\b|\bamd\b", t):
        return "cpu_amd"
    if re.search(r"\bintel\b|\bcore i[3579]\b|\bcore ultra\b", t):
        return "cpu_intel"
    return None


def _classify_ram(title: str) -> str | None:
    t = _norm(title)
    if re.search(r"\bddr5\b", t):
        return "ram_ddr5"
    if re.search(r"\bddr4\b", t):
        return "ram_ddr4"
    return None


def _classify_motherboard(title: str) -> str | None:
    t = _norm(title)
    for brand in ("asus", "msi", "gigabyte"):
        if brand in t:
            return f"motherboard_{brand}"
    return None


def _classify_storage(title: str) -> str | None:
    t = _norm(title)
    if re.search(r"\bnvme\b|\bm\.2\b|\b2280\b", t):
        return "storage_nvme_m2"
    if re.search(r"\bsata\b|2\.5(?:-inch|\s?inch|\")", t):
        return "storage_sata_2_5"
    return None


# ---- GPU: shape-tier, NOT brand — cooler-shroud size is what customers
# actually see; a blower reference card and a triple-fan flagship look
# nothing alike even from the same manufacturer ------------------------------
_GPU_BLOWER_HINTS = ("blower", "reference", "founders edition", "fe ")
_GPU_LARGE_HINTS = (
    "4090", "4080", "3090", "3080", "7900 xtx", "7900 xt", "6900 xt", "6950",
    "triple fan", "3-fan", "3 fan",
)
_GPU_COMPACT_HINTS = ("1650", "1660", "3050", "4060", "6400", "6500", "6600", "low profile", "sff")


def _classify_gpu(title: str) -> str | None:
    t = _norm(title)
    if re.search(r"\brtx\b|\bgtx\b|\bgeforce\b|\bnvidia\b", t):
        return "gpu_nvidia"
    if re.search(r"\bradeon\b|\brx\s?\d|\bamd\b", t):
        return "gpu_amd"
    if re.search(r"\bintel\s+arc\b|\barc\s+[ab]\d", t):
        return "gpu_intel"
    return None


# ---- Cooling: type + size — an AIO's radiator size and an LCD pump are the
# visually dominant features, not the brand -------------------------------
def _classify_cooling(title: str) -> str | None:
    t = _norm(title)
    is_aio = bool(re.search(r"\baio\b|liquid|water cool|radiator|\d{3}\s?mm", t))
    if is_aio:
        has_lcd = "lcd" in t
        if "360" in t:
            size = "360"
        elif "280" in t:
            size = "280"
        elif "240" in t:
            size = "240"
        elif "120" in t:
            size = "120"
        else:
            return None  # radiator size is load-bearing for AIO shape — no guess
        return f"cooling_aio_{size}_lcd" if has_lcd else f"cooling_aio_{size}"
    if re.search(r"\btower cooler\b|\bair cooler\b|\bheatsink\b", t):
        return "cooling_air_tower"
    return None


# ---- Fan: size + blade style ------------------------------------------------
def _classify_fan(title: str) -> str | None:
    t = _norm(title)
    if not re.search(r"\bfan\b", t):
        return None
    size = "120" if "120" in t else ("140" if "140" in t else None)
    if not size:
        return None
    style = "rgb" if re.search(r"\brgb\b|\bargb\b", t) else "plain"
    return f"fan_{size}_{style}"


def _classify_psu(title: str) -> str | None:
    """PSUs share one standard ATX library model unless an exact asset overrides it."""
    t = _norm(title)
    if re.search(r"\bpsu\b|power supply|\d{3,4}\s?w\b|80\+|80 plus", t):
        return "psu_atx_standard"
    return None


_CLASSIFIERS = {
    "cpu": _classify_cpu,
    "ram": _classify_ram,
    "motherboard": _classify_motherboard,
    "gpu": _classify_gpu,
    "cooling": _classify_cooling,
    "fan": _classify_fan,
    "psu": _classify_psu,
    "storage": _classify_storage,
}


def classify_family(category: str, title: str) -> str | None:
    """Returns a family bucket key, or None if this category isn't bucketed
    (psu/storage/os — kept as plain per-category generics) or the title
    doesn't confidently match a known bucket."""
    classifier = _CLASSIFIERS.get(category)
    if not classifier or not title:
        return None
    return classifier(title)


# The full target bucket list this taxonomy can produce — used to drive the
# admin generation UI (one "generate" action per bucket, not per listing).
# Not exhaustive of every possible classify_family() output (brand lists can
# grow), but enough to know what to generate first.
KNOWN_FAMILY_BUCKETS: list[tuple[str, str]] = [
    ("cpu", "cpu_amd"), ("cpu", "cpu_intel"),
    ("motherboard", "motherboard_atx"), ("motherboard", "motherboard_matx"),
    ("motherboard", "motherboard_asus"), ("motherboard", "motherboard_msi"),
    ("motherboard", "motherboard_gigabyte"),
    ("ram", "ram_ddr4"), ("ram", "ram_ddr5"),
    ("gpu", "gpu_nvidia"), ("gpu", "gpu_amd"), ("gpu", "gpu_intel"),
    ("cooling", "cooling_air_tower"),
    ("cooling", "cooling_aio_240"),
    ("storage", "storage_nvme_m2"), ("storage", "storage_sata_2_5"),
    ("psu", "psu_atx_standard"),
]
