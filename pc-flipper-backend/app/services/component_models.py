"""
Canonical component model registry.

This is the single source of truth for which specific component models
we track prices for. The upgrade_parts swarm searches for each of these
models by name, and the catalogue API returns prices for each model across
all sources.

Playbook component_catalogue entries reference model names from this list.
"""
from __future__ import annotations

from typing import TypedDict


class ComponentModel(TypedDict):
    name: str          # canonical display name (also the eBay search term)
    bh_search: str     # BargainHardware URL query string
    tier: str          # budget | mid | high | ultra


CANONICAL_MODELS: dict[str, list[ComponentModel]] = {
    "gpu": [
        # Budget
        {"name": "RTX 3060 12GB",        "bh_search": "rtx+3060+12gb",       "tier": "budget"},
        {"name": "RTX 3060 Ti 8GB",      "bh_search": "rtx+3060+ti+8gb",     "tier": "budget"},
        {"name": "RX 6600 8GB",          "bh_search": "rx+6600+8gb",         "tier": "budget"},
        {"name": "RX 6600 XT 8GB",       "bh_search": "rx+6600+xt+8gb",      "tier": "budget"},
        {"name": "RTX 2070 Super 8GB",   "bh_search": "rtx+2070+super+8gb",  "tier": "budget"},
        # Mid
        {"name": "RTX 3070 8GB",         "bh_search": "rtx+3070+8gb",        "tier": "mid"},
        {"name": "RTX 3070 Ti 8GB",      "bh_search": "rtx+3070+ti+8gb",     "tier": "mid"},
        {"name": "RX 6700 XT 12GB",      "bh_search": "rx+6700+xt+12gb",     "tier": "mid"},
        {"name": "RX 6800 16GB",         "bh_search": "rx+6800+16gb",        "tier": "mid"},
        {"name": "RTX 4060 8GB",         "bh_search": "rtx+4060+8gb",        "tier": "mid"},
        {"name": "RTX 4060 Ti 8GB",      "bh_search": "rtx+4060+ti+8gb",     "tier": "mid"},
        {"name": "RX 7600 8GB",          "bh_search": "rx+7600+8gb",         "tier": "mid"},
        # High
        {"name": "RTX 3080 10GB",        "bh_search": "rtx+3080+10gb",       "tier": "high"},
        {"name": "RTX 3080 Ti 12GB",     "bh_search": "rtx+3080+ti+12gb",    "tier": "high"},
        {"name": "RX 6800 XT 16GB",      "bh_search": "rx+6800+xt+16gb",     "tier": "high"},
        {"name": "RTX 4070 12GB",        "bh_search": "rtx+4070+12gb",       "tier": "high"},
        {"name": "RTX 4070 Super 12GB",  "bh_search": "rtx+4070+super+12gb", "tier": "high"},
        {"name": "RX 7800 XT 16GB",      "bh_search": "rx+7800+xt+16gb",     "tier": "high"},
        {"name": "RTX 4070 Ti 12GB",     "bh_search": "rtx+4070+ti+12gb",    "tier": "high"},
        # Ultra
        {"name": "RTX 3090 24GB",        "bh_search": "rtx+3090+24gb",       "tier": "ultra"},
        {"name": "RTX 4080 16GB",        "bh_search": "rtx+4080+16gb",       "tier": "ultra"},
        {"name": "RTX 4090 24GB",        "bh_search": "rtx+4090+24gb",       "tier": "ultra"},
        {"name": "RX 7900 XTX 24GB",     "bh_search": "rx+7900+xtx+24gb",    "tier": "ultra"},
    ],
    "cpu": [
        # Intel — Budget
        {"name": "Intel Core i3-12100",   "bh_search": "intel+i3-12100",   "tier": "budget"},
        {"name": "Intel Core i5-10400",   "bh_search": "intel+i5-10400",   "tier": "budget"},
        {"name": "Intel Core i5-10400F",  "bh_search": "intel+i5-10400f",  "tier": "budget"},
        {"name": "Intel Core i5-12400",   "bh_search": "intel+i5-12400",   "tier": "budget"},
        {"name": "Intel Core i5-12400F",  "bh_search": "intel+i5-12400f",  "tier": "budget"},
        # Intel — Mid
        {"name": "Intel Core i5-12600K",  "bh_search": "intel+i5-12600k",  "tier": "mid"},
        {"name": "Intel Core i5-13600K",  "bh_search": "intel+i5-13600k",  "tier": "mid"},
        {"name": "Intel Core i7-12700K",  "bh_search": "intel+i7-12700k",  "tier": "mid"},
        # Intel — High
        {"name": "Intel Core i7-13700K",  "bh_search": "intel+i7-13700k",  "tier": "high"},
        {"name": "Intel Core i9-12900K",  "bh_search": "intel+i9-12900k",  "tier": "high"},
        {"name": "Intel Core i9-13900K",  "bh_search": "intel+i9-13900k",  "tier": "high"},
        # AMD — Budget
        {"name": "AMD Ryzen 5 3600",      "bh_search": "ryzen+5+3600",      "tier": "budget"},
        {"name": "AMD Ryzen 5 5600",      "bh_search": "ryzen+5+5600",      "tier": "budget"},
        {"name": "AMD Ryzen 5 5600X",     "bh_search": "ryzen+5+5600x",     "tier": "budget"},
        {"name": "AMD Ryzen 5 7600",      "bh_search": "ryzen+5+7600",      "tier": "budget"},
        # AMD — Mid
        {"name": "AMD Ryzen 7 5700X",     "bh_search": "ryzen+7+5700x",     "tier": "mid"},
        {"name": "AMD Ryzen 7 7700X",     "bh_search": "ryzen+7+7700x",     "tier": "mid"},
        {"name": "AMD Ryzen 7 7800X3D",   "bh_search": "ryzen+7+7800x3d",   "tier": "mid"},
        # AMD — High
        {"name": "AMD Ryzen 9 5900X",     "bh_search": "ryzen+9+5900x",     "tier": "high"},
        {"name": "AMD Ryzen 9 5950X",     "bh_search": "ryzen+9+5950x",     "tier": "high"},
        {"name": "AMD Ryzen 9 7900X",     "bh_search": "ryzen+9+7900x",     "tier": "high"},
        {"name": "AMD Ryzen 9 7950X",     "bh_search": "ryzen+9+7950x",     "tier": "ultra"},
    ],
    "ram": [
        {"name": "16GB DDR4 3200MHz Kit",  "bh_search": "16gb+ddr4+3200+kit",  "tier": "budget"},
        {"name": "32GB DDR4 3200MHz Kit",  "bh_search": "32gb+ddr4+3200+kit",  "tier": "mid"},
        {"name": "64GB DDR4 3200MHz Kit",  "bh_search": "64gb+ddr4+3200+kit",  "tier": "high"},
        {"name": "16GB DDR5 5600MHz Kit",  "bh_search": "16gb+ddr5+5600+kit",  "tier": "budget"},
        {"name": "32GB DDR5 5600MHz Kit",  "bh_search": "32gb+ddr5+5600+kit",  "tier": "mid"},
        {"name": "64GB DDR5 5600MHz Kit",  "bh_search": "64gb+ddr5+5600+kit",  "tier": "high"},
        {"name": "128GB DDR4 ECC Kit",     "bh_search": "128gb+ddr4+ecc+kit",  "tier": "ultra"},
    ],
    "ssd": [
        {"name": "500GB NVMe M.2 SSD",    "bh_search": "500gb+nvme+m2+ssd",   "tier": "budget"},
        {"name": "1TB NVMe M.2 SSD",      "bh_search": "1tb+nvme+m2+ssd",     "tier": "budget"},
        {"name": "2TB NVMe M.2 SSD",      "bh_search": "2tb+nvme+m2+ssd",     "tier": "mid"},
        {"name": "4TB NVMe M.2 SSD",      "bh_search": "4tb+nvme+m2+ssd",     "tier": "high"},
        {"name": "500GB SATA SSD",        "bh_search": "500gb+sata+ssd",      "tier": "budget"},
        {"name": "1TB SATA SSD",          "bh_search": "1tb+sata+ssd",        "tier": "budget"},
        {"name": "2TB SATA SSD",          "bh_search": "2tb+sata+ssd",        "tier": "mid"},
    ],
    "psu": [
        {"name": "550W 80+ Bronze ATX PSU",   "bh_search": "550w+80plus+bronze+atx",   "tier": "budget"},
        {"name": "650W 80+ Bronze ATX PSU",   "bh_search": "650w+80plus+bronze+atx",   "tier": "budget"},
        {"name": "650W 80+ Gold ATX PSU",     "bh_search": "650w+80plus+gold+atx",     "tier": "mid"},
        {"name": "750W 80+ Gold ATX PSU",     "bh_search": "750w+80plus+gold+atx",     "tier": "mid"},
        {"name": "850W 80+ Gold ATX PSU",     "bh_search": "850w+80plus+gold+atx",     "tier": "high"},
        {"name": "1000W 80+ Gold ATX PSU",    "bh_search": "1000w+80plus+gold+atx",    "tier": "high"},
        {"name": "850W 80+ Platinum ATX PSU", "bh_search": "850w+80plus+platinum+atx", "tier": "ultra"},
    ],
    "motherboard": [
        # LGA1700 (12th/13th gen Intel)
        {"name": "H610 mATX Motherboard LGA1700",  "bh_search": "h610+matx+lga1700",  "tier": "budget"},
        {"name": "B660 ATX Motherboard LGA1700",   "bh_search": "b660+atx+lga1700",   "tier": "budget"},
        {"name": "B760 ATX Motherboard LGA1700",   "bh_search": "b760+atx+lga1700",   "tier": "budget"},
        {"name": "Z690 ATX Motherboard LGA1700",   "bh_search": "z690+atx+lga1700",   "tier": "mid"},
        {"name": "Z790 ATX Motherboard LGA1700",   "bh_search": "z790+atx+lga1700",   "tier": "high"},
        # AM4 (Ryzen 3000/5000)
        {"name": "B550 ATX Motherboard AM4",       "bh_search": "b550+atx+am4",       "tier": "budget"},
        {"name": "X570 ATX Motherboard AM4",       "bh_search": "x570+atx+am4",       "tier": "mid"},
        # AM5 (Ryzen 7000)
        {"name": "B650 ATX Motherboard AM5",       "bh_search": "b650+atx+am5",       "tier": "mid"},
        {"name": "X670E ATX Motherboard AM5",      "bh_search": "x670e+atx+am5",      "tier": "high"},
    ],
    "cooler": [
        {"name": "Cooler Master Hyper 212",            "bh_search": "cooler+master+hyper+212",         "tier": "budget"},
        {"name": "Deepcool AK400",                     "bh_search": "deepcool+ak400",                  "tier": "budget"},
        {"name": "Thermalright Peerless Assassin 120", "bh_search": "thermalright+peerless+assassin",  "tier": "budget"},
        {"name": "Deepcool AK620",                     "bh_search": "deepcool+ak620",                  "tier": "mid"},
        {"name": "be quiet! Dark Rock 4",              "bh_search": "be+quiet+dark+rock+4",            "tier": "mid"},
        {"name": "Noctua NH-U12S",                     "bh_search": "noctua+nh-u12s",                  "tier": "mid"},
        {"name": "Noctua NH-D15",                      "bh_search": "noctua+nh-d15",                   "tier": "high"},
        {"name": "be quiet! Dark Rock Pro 4",          "bh_search": "be+quiet+dark+rock+pro+4",        "tier": "high"},
        {"name": "ARCTIC Liquid Freezer II 240",       "bh_search": "arctic+liquid+freezer+240",       "tier": "mid"},
        {"name": "Corsair H100i RGB 240mm AIO",        "bh_search": "corsair+h100i+240mm",             "tier": "mid"},
        {"name": "NZXT Kraken X53 240mm AIO",          "bh_search": "nzxt+kraken+x53+240mm",           "tier": "high"},
    ],
}

# Flat lookup: model name → (category, tier)
_MODEL_LOOKUP: dict[str, tuple[str, str]] = {
    m["name"]: (cat, m["tier"])
    for cat, models in CANONICAL_MODELS.items()
    for m in models
}


def all_model_names() -> list[str]:
    """Return all canonical model names across all categories."""
    return [m["name"] for models in CANONICAL_MODELS.values() for m in models]


def model_category(name: str) -> str | None:
    """Return the category for a canonical model name, or None if not found."""
    return _MODEL_LOOKUP.get(name, (None, None))[0]


def model_tier(name: str) -> str | None:
    """Return the tier for a canonical model name, or None if not found."""
    return _MODEL_LOOKUP.get(name, (None, None))[1]


# Maps playbook target_use_case → which tiers of each component are relevant.
# Used to populate playbook.component_catalogue.
PLAYBOOK_COMPONENT_MAP: dict[str, dict[str, list[str]]] = {
    "ultra_budget": {
        "cpu":         ["budget"],
        "ram":         ["budget"],
        "ssd":         ["budget"],
        "psu":         ["budget"],
        "motherboard": ["budget"],
        "cooler":      ["budget"],
    },
    "budget_gaming": {
        "gpu":         ["budget"],
        "cpu":         ["budget"],
        "ram":         ["budget"],
        "ssd":         ["budget"],
        "psu":         ["budget"],
        "motherboard": ["budget"],
        "cooler":      ["budget"],
    },
    "mid_gaming": {
        "gpu":         ["budget", "mid"],
        "cpu":         ["budget", "mid"],
        "ram":         ["budget", "mid"],
        "ssd":         ["budget", "mid"],
        "psu":         ["budget", "mid"],
        "motherboard": ["budget", "mid"],
        "cooler":      ["budget", "mid"],
    },
    "high_gaming": {
        "gpu":         ["mid", "high"],
        "cpu":         ["mid", "high"],
        "ram":         ["mid"],
        "ssd":         ["mid"],
        "psu":         ["mid", "high"],
        "motherboard": ["mid", "high"],
        "cooler":      ["mid", "high"],
    },
    "content_creation": {
        "gpu":         ["high"],
        "cpu":         ["high"],
        "ram":         ["high"],
        "ssd":         ["mid", "high"],
        "psu":         ["high"],
        "motherboard": ["mid", "high"],
        "cooler":      ["high"],
    },
    "ai_workstation": {
        "gpu":         ["ultra"],
        "cpu":         ["high", "ultra"],
        "ram":         ["high", "ultra"],
        "ssd":         ["high"],
        "psu":         ["ultra"],
        "motherboard": ["high"],
        "cooler":      ["high"],
    },
    "office": {
        "cpu":         ["budget"],
        "ram":         ["budget"],
        "ssd":         ["budget"],
        "psu":         ["budget"],
        "motherboard": ["budget"],
        "cooler":      ["budget"],
    },
}


def catalogue_for_use_case(use_case: str) -> dict[str, list[str]]:
    """
    Return a component_catalogue dict (category → list of model names)
    for a given use_case key.
    """
    tier_map = PLAYBOOK_COMPONENT_MAP.get(use_case, PLAYBOOK_COMPONENT_MAP["mid_gaming"])
    result: dict[str, list[str]] = {}
    for cat, tiers in tier_map.items():
        models = [
            m["name"]
            for m in CANONICAL_MODELS.get(cat, [])
            if m["tier"] in tiers
        ]
        if models:
            result[cat] = models
    return result
