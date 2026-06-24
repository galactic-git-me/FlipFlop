"""
Per-category, tier-aware gem scoring for the parts catalogue.

Logic:
  1. Consider only parts from trusted sources (eBay UK, Gumtree, Amazon).
  2. Within each category, split parts into three price tiers using tertiles
     so that a cheap GPU is compared against other cheap GPUs, not against RAM.
  3. Within each tier, compute the median price.
  4. Score each part as: discount_pct = (tier_median - price) / tier_median * 100
     - discount_pct >= 35 → super_gem
     - discount_pct >= 20 → gem
     - otherwise → None

This scales naturally: a GPU at £80 when the budget-GPU median is £130 (38%
off) earns Super Gem, while a RAM stick at £10 when the budget-RAM median
is £16 (37% off) also earns Super Gem — without any hard-coded price tables.
"""

import statistics
from collections import defaultdict

GOOD_SOURCES: frozenset[str] = frozenset({"eBay UK", "Gumtree", "Amazon"})

# Sanity bounds per category — removes obvious scraping junk and retail listings.
CATEGORY_BOUNDS: dict[str, tuple[float, float]] = {
    "gpu":         (20,   1500),
    "ram":         (8,    500),
    "ssd":         (8,    600),
    "cpu":         (15,   1000),
    "psu":         (10,   400),
    "motherboard": (15,   600),
    "case":        (15,   400),
    "cooler":      (5,    200),
    "accessory":   (5,    200),
}

GEM_THRESHOLD       = 20.0   # % below tier median → gem
SUPER_GEM_THRESHOLD = 35.0   # % below tier median → super gem
MIN_TIER_SIZE       = 3      # skip a tier if fewer than this many parts in it


def score_groups(groups: list[dict]) -> dict[str, dict]:
    """
    Parameters
    ----------
    groups : list[dict]
        Each dict must have 'category', 'cheapest_good_price' (float | None),
        and a unique key (we use category + name).

    Returns
    -------
    dict[key → {"gem_classification": str|None, "gem_score": float|None}]
    where key = f"{category}::{name}".
    """

    # Build reference distribution: cheapest_good_price per category
    by_category: dict[str, list[tuple[str, float]]] = defaultdict(list)
    for g in groups:
        cat = g.get("category", "")
        price = g.get("cheapest_good_price")
        if price is None:
            continue
        lo, hi = CATEGORY_BOUNDS.get(str(cat), (0, 9_999_999))
        if not (lo <= price <= hi):
            continue
        key = f"{cat}::{g['name']}"
        by_category[str(cat)].append((key, price))

    results: dict[str, dict] = {}

    for cat, items in by_category.items():
        if len(items) < MIN_TIER_SIZE * 3:
            # Too few items to divide into 3 meaningful tiers; use whole category
            tiers = [items]
        else:
            items_sorted = sorted(items, key=lambda x: x[1])
            n = len(items_sorted)
            cut1 = n // 3
            cut2 = 2 * n // 3
            tiers = [
                items_sorted[:cut1],
                items_sorted[cut1:cut2],
                items_sorted[cut2:],
            ]

        for tier in tiers:
            if len(tier) < MIN_TIER_SIZE:
                continue
            prices = [p for _, p in tier]
            median = statistics.median(prices)
            if median <= 0:
                continue
            for key, price in tier:
                discount = (median - price) / median * 100
                if discount >= SUPER_GEM_THRESHOLD:
                    classification = "super_gem"
                elif discount >= GEM_THRESHOLD:
                    classification = "gem"
                else:
                    classification = None
                results[key] = {
                    "gem_classification": classification,
                    "gem_score": round(discount, 1),
                }

    return results
