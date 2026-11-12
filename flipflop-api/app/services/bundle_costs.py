"""Deterministic accounting allocations for verified multi-component offers.

Allocated component values describe the bundle purchase's accounting split;
they are not independently purchasable supplier offers.
"""
from __future__ import annotations

from decimal import Decimal, ROUND_DOWN
from typing import Mapping

PENNY = Decimal("0.01")


def allocate_bundle_cost(
    total_cost: Decimal,
    reference_prices: Mapping[str, Decimal],
) -> dict[str, Decimal]:
    """Allocate a bundle total by reference-price share, reconciling pennies.

    Keys must be stable component identities. Any rounding remainder is
    assigned in key order, so repeated runs produce identical allocations.
    """
    total = Decimal(total_cost).quantize(PENNY)
    references = {key: Decimal(value) for key, value in reference_prices.items()}
    if not references:
        raise ValueError("at least one component reference price is required")
    if any(not key for key in references):
        raise ValueError("component identities must be non-empty")
    if total < 0 or any(value <= 0 for value in references.values()):
        raise ValueError("bundle cost must be non-negative and references positive")

    reference_total = sum(references.values(), Decimal("0"))
    allocations = {
        key: (total * value / reference_total).quantize(PENNY, rounding=ROUND_DOWN)
        for key, value in references.items()
    }
    remainder = int((total - sum(allocations.values())).scaleb(2))
    for key in sorted(allocations)[:remainder]:
        allocations[key] += PENNY
    return allocations
