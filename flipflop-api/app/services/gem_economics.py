"""Conservative, evidence-led Gem Hunter acquisition economics."""
from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP


MONEY = Decimal("0.01")


@dataclass(frozen=True)
class GemCosts:
    asking_price: Decimal
    inbound_delivery: Decimal
    buyer_protection: Decimal
    repairs_and_upgrades: Decimal
    build_labour: Decimal
    outbound_delivery: Decimal
    marketplace_fees: Decimal
    warranty_and_returns_reserve: Decimal
    risk_reserve: Decimal

    @property
    def all_in(self) -> Decimal:
        return sum((getattr(self, field) for field in self.__dataclass_fields__), Decimal("0"))


def assess_gem(
    costs: GemCosts,
    conservative_resale: Decimal,
    minimum_net_contribution: Decimal,
    estimated_days_to_sell: int | None,
    remaining_speculative_budget: Decimal,
    *, sold_sample_size: int,
) -> dict:
    values = [*(getattr(costs, field) for field in costs.__dataclass_fields__), conservative_resale,
              minimum_net_contribution, remaining_speculative_budget]
    if any(value < 0 for value in values):
        raise ValueError("Gem economics cannot contain negative costs or values")
    non_purchase = costs.all_in - costs.asking_price
    max_buy = max(Decimal("0"), conservative_resale - non_purchase - minimum_net_contribution)
    max_buy = min(max_buy, remaining_speculative_budget).quantize(MONEY, rounding=ROUND_HALF_UP)
    net = (conservative_resale - costs.all_in).quantize(MONEY, rounding=ROUND_HALF_UP)
    evidence_ok = sold_sample_size >= 3 and estimated_days_to_sell is not None and estimated_days_to_sell > 0
    return {
        "acquisition_price_gbp": costs.asking_price,
        "all_in_cost_gbp": costs.all_in.quantize(MONEY, rounding=ROUND_HALF_UP),
        "conservative_resale_gbp": conservative_resale,
        "net_contribution_gbp": net,
        "max_buy_price_gbp": max_buy,
        "profit_velocity_gbp_per_day": (net / estimated_days_to_sell).quantize(MONEY, rounding=ROUND_HALF_UP) if evidence_ok else None,
        "decision": "review" if evidence_ok and net >= minimum_net_contribution and costs.asking_price <= max_buy else "ignore",
        "confidence": "evidenced" if evidence_ok else "insufficient_evidence",
        "autonomous_purchase_allowed": False,
    }
