"""Deterministic vNext offerability rules. Monetary inputs use GBP Decimal.

Only evidenced supplier and market data should be passed to these functions.
This module makes no stock, delivery or finance eligibility claims.
"""
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from decimal import Decimal, ROUND_HALF_UP
from enum import Enum


MONEY = Decimal("0.01")


class Condition(str, Enum):
    NEW = "new"
    REFURBISHED = "refurbished"
    USED = "used"


class ConditionPolicy(str, Enum):
    NEW_ONLY = "NEW_ONLY"
    NEW_OR_REFURBISHED = "NEW_OR_REFURBISHED"
    USED_ALLOWED = "USED_ALLOWED"


class FulfilmentMode(str, Enum):
    PRIORITY = "priority"
    STANDARD = "standard"
    FLEXIBLE = "flexible"
    READY_TO_SHIP = "ready_to_ship"


@dataclass(frozen=True)
class SupplierOffer:
    supplier: str
    channel: str  # retail or marketplace
    condition: Condition
    item_gbp: Decimal
    delivery_gbp: Decimal
    fees_gbp: Decimal
    risk_gbp: Decimal
    observed_at: str
    stock_confirmed: bool
    approved: bool
    delivery_working_days: int | None = None
    supplier_confidence: Decimal = Decimal("1")

    @property
    def landed_gbp(self) -> Decimal:
        return self.item_gbp + self.delivery_gbp + self.fees_gbp


@dataclass(frozen=True)
class CostStack:
    landed_parts: Decimal
    build_labour: Decimal
    packaging: Decimal
    outbound_delivery: Decimal
    payment_cost: Decimal
    warranty_reserve: Decimal
    returns_reserve: Decimal
    expected_failure_cost: Decimal
    allocated_overhead: Decimal
    other_variable_costs: Decimal = Decimal("0")

    @property
    def true_cost(self) -> Decimal:
        return sum((getattr(self, field) for field in self.__dataclass_fields__), Decimal("0"))


@dataclass(frozen=True)
class MarketEvidence:
    condition: Condition
    sold_median_gbp: Decimal | None
    sold_sample_size: int
    observed_at: str | None
    active_median_gbp: Decimal | None = None


@dataclass(frozen=True)
class PriceDecision:
    offerable: bool
    price_gbp: Decimal | None
    required_base_gbp: Decimal
    reason: str


def condition_allowed(policy: ConditionPolicy, condition: Condition, consent: bool) -> bool:
    if condition == Condition.NEW:
        return True
    if not consent:
        return False
    if policy == ConditionPolicy.NEW_OR_REFURBISHED:
        return condition == Condition.REFURBISHED
    return policy == ConditionPolicy.USED_ALLOWED


def supplier_allowed(mode: FulfilmentMode, offer: SupplierOffer) -> bool:
    if not offer.approved or offer.supplier_confidence < Decimal("0.8"):
        return False
    if mode == FulfilmentMode.PRIORITY:
        return offer.channel == "retail" and offer.supplier.strip().lower() in {"amazon", "overclockers uk", "overclockers"}
    if mode == FulfilmentMode.STANDARD:
        return offer.channel == "retail"
    return True


def eligible_offers(
    offers: list[SupplierOffer], mode: FulfilmentMode, policy: ConditionPolicy, consent: bool,
    *, priority_capacity: bool = False, now: datetime | None = None,
) -> list[SupplierOffer]:
    if mode == FulfilmentMode.PRIORITY and not priority_capacity:
        return []
    if mode == FulfilmentMode.READY_TO_SHIP:
        return []
    now = now or datetime.now(timezone.utc)
    filtered = [
        offer for offer in offers
        if offer.stock_confirmed
        and _recent(offer.observed_at, now, timedelta(hours=24))
        and supplier_allowed(mode, offer)
        and condition_allowed(policy, offer.condition, consent)
        and (mode != FulfilmentMode.PRIORITY or (offer.delivery_working_days is not None and offer.delivery_working_days <= 1))
        and (mode != FulfilmentMode.STANDARD or (offer.delivery_working_days is not None and offer.delivery_working_days <= 3))
    ]
    return sorted(filtered, key=lambda offer: offer.landed_gbp + offer.risk_gbp)


def _recent(value: str | None, now: datetime, maximum_age: timedelta) -> bool:
    if not value:
        return False
    try:
        observed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return False
    if observed.tzinfo is None:
        observed = observed.replace(tzinfo=timezone.utc)
    return timedelta(0) <= now - observed <= maximum_age


def evaluate_price(
    costs: CostStack,
    market: MarketEvidence,
    condition: Condition,
    minimum_contribution_gbp: Decimal,
    minimum_margin_fraction: Decimal,
    *, premium_gbp: Decimal = Decimal("0"),
    market_tolerance_fraction: Decimal = Decimal("0.10"),
    now: datetime | None = None,
) -> PriceDecision:
    values = [*(getattr(costs, field) for field in costs.__dataclass_fields__), minimum_contribution_gbp, premium_gbp]
    if any(value < 0 for value in values) or not 0 <= minimum_margin_fraction < 1 or market_tolerance_fraction < 0:
        raise ValueError("Costs, contribution, premium and market tolerance must be nonnegative; margin must be below 1")
    true_cost = costs.true_cost
    base = max(true_cost + minimum_contribution_gbp, true_cost / (1 - minimum_margin_fraction))
    base = base.quantize(MONEY, rounding=ROUND_HALF_UP)
    required = (base + premium_gbp).quantize(MONEY, rounding=ROUND_HALF_UP)
    if condition != market.condition:
        return PriceDecision(False, None, base, "Market evidence condition does not match the build")
    if market.sold_median_gbp is None or market.sold_sample_size < 3 or not _recent(market.observed_at, now or datetime.now(timezone.utc), timedelta(days=30)):
        return PriceDecision(False, None, base, "Insufficient sold-market evidence")
    if required > market.sold_median_gbp * (1 + market_tolerance_fraction):
        return PriceDecision(False, None, base, "Required price is not commercially credible against sold evidence")
    return PriceDecision(True, required, base, "True cost, contribution and sold-market gates passed")
