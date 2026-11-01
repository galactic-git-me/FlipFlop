"""Pure same-specification delivery economics. No purchasing or provider effects."""
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from decimal import Decimal, ROUND_CEILING, ROUND_FLOOR

from app.schemas.commercial_quote import CellCommercialPolicy
from app.services.commerce_pricing import (
    ConditionPolicy, FulfilmentMode, SupplierOffer, _recent, eligible_offers,
)

from app.services.commercial_pilot_policy import MINIMUM_PROFIT_MARGIN

PENNY = Decimal("0.01")
MODES = {"fast_track": FulfilmentMode.PRIORITY,
         "standard": FulfilmentMode.STANDARD, "flexible": FulfilmentMode.FLEXIBLE}


@dataclass(frozen=True)
class PartEvidence:
    evidence_id: int
    part_key: str
    offer: SupplierOffer


@dataclass(frozen=True)
class CapacityEvidence:
    evidence_id: int | None
    observed_at: str
    available: bool
    # Working days until the evidenced workshop week can start.
    wait_working_days: int


def _up(value: Decimal) -> Decimal:
    return value.quantize(PENNY, rounding=ROUND_CEILING)


def _aware_recent(value, now, maximum_age):
    try:
        observed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return observed.tzinfo is not None and _recent(value, now, maximum_age)
    except (ValueError, AttributeError):
        return False


def _economics(policy, fixed, price):
    net = (price / (1 + policy.vat_rate)).quantize(PENNY, rounding=ROUND_FLOOR)
    charges = {name: _up(price * getattr(policy, name))
               for name in ("payment_rate", "warranty_rate", "returns_rate")}
    true_cost = fixed + sum(charges.values(), Decimal(0))
    contribution = net - true_cost
    return net, charges, true_cost, contribution


def supplier_meets_delivery_commitment(supplier_days, mode, *, workshop_wait_days=0):
    """All parts must arrive before the full customer delivery deadline."""
    if mode.maximum_delivery_working_days is None:
        return True  # Flexible pace has no customer delivery commitment.
    return (isinstance(supplier_days,int) and not isinstance(supplier_days,bool) and supplier_days>=0
        and isinstance(workshop_wait_days,int) and not isinstance(workshop_wait_days,bool) and workshop_wait_days>=0
        and max(supplier_days,workshop_wait_days)+mode.workshop_working_days+mode.courier_working_days
            <= mode.maximum_delivery_working_days)


def quote_delivery_modes(
    policy: CellCommercialPolicy, parts: list[PartEvidence],
    capacities: dict[str, CapacityEvidence | None], *,
    nonnew_consent: bool = False, now: datetime | None = None,
) -> dict:
    """Assess approved core BOM keys. Availability here is not payment authority.

    Supplier inputs must be the latest observation of each source listing.
    The adapter owns canonical BOM mapping and current capacity resolution.
    """
    now = now or datetime.now(timezone.utc)
    if now.tzinfo is None:
        raise ValueError("Quote time must be timezone-aware")
    result = {"policy_version": policy.version, "created_at": now.isoformat(),
              "purchasable": False, "modes": {}}
    condition_policy = ConditionPolicy.USED_ALLOWED  # exact condition still enforced below
    for name, fulfilment in MODES.items():
        def reject(reason):
            return {"offerable": False, "price_gbp": None, "reason": reason}

        if name not in policy.enabled_modes:
            result["modes"][name] = reject("This delivery option is not enabled by the Playbook policy")
            continue

        capacity = capacities.get(name)
        capacity_missing = name not in capacities
        if (capacity is not None and (not capacity.available or capacity.wait_working_days < 0
                or not _aware_recent(capacity.observed_at, now, timedelta(hours=24)))):
            # A stale optional calendar hint is ignored; it never blocks a sale.
            capacity = None
        workshop_wait_days = capacity.wait_working_days if capacity is not None else 0
        mode = policy.modes[name]
        selected = []
        for key in policy.required_part_keys:
            candidates = [part for part in parts if part.part_key == key
                          and part.offer.condition == policy.condition
                          and part.offer.supplier_confidence.is_finite()
                          and Decimal(0) <= part.offer.supplier_confidence <= Decimal(1)
                          and _aware_recent(part.offer.observed_at, now, timedelta(hours=24))
                          and all(value.is_finite() and value >= 0 for value in (
                              part.offer.item_gbp, part.offer.delivery_gbp,
                              part.offer.fees_gbp, part.offer.risk_gbp))]
            valid = eligible_offers(
                [part.offer for part in candidates], fulfilment, condition_policy,
                nonnew_consent, priority_capacity=True, now=now,
            )
            # Unknown/negative supplier time cannot support an end-to-end estimate.
            valid = [offer for offer in valid if name=='flexible' or supplier_meets_delivery_commitment(
                offer.delivery_working_days,mode,workshop_wait_days=workshop_wait_days)]
            if not valid:
                selected = []
                break
            offer = valid[0]
            selected.append(next(part for part in candidates if part.offer is offer))
        if not selected:
            result["modes"][name] = reject("Exact-spec supplier evidence is missing, stale or cannot meet this mode")
            continue
        landed = sum(((part.offer.landed_gbp + part.offer.risk_gbp)
            * policy.part_quantities.get(part.part_key,1) for part in selected), Decimal(0))
        values = [value for part in selected for value in (
            part.offer.item_gbp, part.offer.delivery_gbp, part.offer.fees_gbp, part.offer.risk_gbp)]
        if any(not value.is_finite() or value < 0 for value in values):
            result["modes"][name] = reject("Supplier costs are invalid")
            continue
        economics = mode_economics(policy, mode, landed)
        price, floor = economics['price'], economics['floor']
        net, charges, true_cost, contribution = (economics[key] for key in ('net','charges','true_cost','contribution'))
        if price <= 0:
            result["modes"][name] = reject("A positive selling price is required")
            continue
        market = policy.market
        if market is not None and not _recent(market.observed_at, now, timedelta(days=30)):
            result["modes"][name] = reject("Current sold-market evidence is required")
            continue
        market_ceiling = (market.sold_p75_gbp if market and market.sold_p75_gbp is not None
                          else market.sold_median_gbp if market else None)
        if market_ceiling is not None and price > market_ceiling * (1 + policy.market_tolerance_fraction):
            result["modes"][name] = reject("Profitable price exceeds the evidenced market ceiling")
            continue
        expiry_candidates = [
            now + timedelta(minutes=15),
            *([datetime.fromisoformat(market.observed_at.replace("Z", "+00:00")) + timedelta(days=30)] if market else []),
            *(datetime.fromisoformat(part.offer.observed_at.replace("Z", "+00:00"))
              + timedelta(hours=24) for part in selected),
        ]
        if capacity is not None:
            expiry_candidates.append(
                datetime.fromisoformat(capacity.observed_at.replace("Z", "+00:00")) + timedelta(hours=24))
        expiry = min(expiry_candidates)
        if expiry <= now:
            result["modes"][name] = reject("Evidence has expired")
            continue
        result["modes"][name] = {
            "part_quantities": {part.part_key:policy.part_quantities.get(part.part_key,1) for part in selected},
            "offerable": True, "price_gbp": str(price), "profit_floor_gbp": str(floor),
            "net_revenue_gbp": str(net), "true_cost_gbp": str(true_cost),
            "contribution_gbp": str(contribution),
            "margin_fraction": str(contribution / net),
            "sale_based_costs_gbp": {key: str(value) for key, value in charges.items()},
            "fixed_costs_gbp": {**{key: str(value) for key, value in mode.costs.model_dump().items()},
                                "landed_parts_including_risk": str(landed)},
            "supplier_offer_ids": [part.evidence_id for part in selected],
            "capacity_evidence_id": capacity.evidence_id if capacity is not None else None,
            "delivery_estimate_kind": "supplier_and_reviewed_workshop_policy",
            "supplier_arrival_working_days": max((part.offer.delivery_working_days for part in selected
                if part.offer.delivery_working_days is not None),default=None),
            "workshop_wait_working_days": workshop_wait_days,
            "workshop_working_days": mode.workshop_working_days,
            "courier_working_days": mode.courier_working_days,
            "maximum_delivery_working_days": None if name=='flexible' else mode.maximum_delivery_working_days,
            "delivery_promised": name!='flexible',
            "delivery_working_days": None if name=='flexible' else max(max(part.offer.delivery_working_days for part in selected),
                                         capacity.wait_working_days if capacity is not None else 0)
                                     + mode.workshop_working_days + mode.courier_working_days,
            "expires_at": expiry.isoformat(),
            "reason": "Exact specification, evidence, delivery and profit checks passed",
            "market_check": "comparable_sold_evidence" if market else "not_configured",
        }
    standard = result["modes"]["standard"]
    for name, quote in result["modes"].items():
        quote["difference_from_standard_gbp"] = None
        if quote["offerable"] and standard["offerable"]:
            difference = Decimal(quote["price_gbp"]) - Decimal(standard["price_gbp"])
            quote["difference_from_standard_gbp"] = str(difference)
            if name == "flexible" and difference >= 0:
                quote.update(offerable=False, price_gbp=None,
                             reason="Flexible does not provide a genuine saving against Standard")
            if name == "fast_track" and (difference <= 0 or quote["delivery_working_days"] >= standard["delivery_working_days"]):
                quote.update(offerable=False, price_gbp=None,
                             reason="Fast Track must be faster and priced above Standard")
        elif name == "flexible" and quote["offerable"]:
            # A missing/invalid Standard mode must not leave an apparent saving
            # comparison available to callers that only inspect offerable modes.
            quote.update(offerable=False, price_gbp=None,
                         reason="A valid Standard quote is required to evidence Flexible savings")
    return result


def mode_economics(policy, mode, landed):
    minimum_margin = max(MINIMUM_PROFIT_MARGIN, mode.minimum_margin_fraction)
    fixed = landed + sum(mode.costs.model_dump().values(), Decimal(0))
    net_fraction = Decimal(1) / (1 + policy.vat_rate)
    rates = policy.payment_rate + policy.warranty_rate + policy.returns_rate
    floor = _up(max(
        (fixed + mode.minimum_contribution_gbp) / (net_fraction - rates),
        fixed / (net_fraction * (1 - minimum_margin) - rates),
    ))
    # Account for rounding each fee/reserve up and net revenue down.
    while True:
        net, charges, true_cost, contribution = _economics(policy, fixed, floor)
        if (contribution >= mode.minimum_contribution_gbp
                and contribution >= net * minimum_margin):
            break
        floor += PENNY
    price = floor + mode.premium_gbp
    net, charges, true_cost, contribution = _economics(policy, fixed, price)
    return {"price": price, "floor": floor, "net": net, "charges": charges, "true_cost": true_cost, "contribution": contribution}


def check_price_profit(policy, mode, landed, price):
    """Deterministic margin check, including sale-dependent fees/reserves."""
    minimum_margin = max(MINIMUM_PROFIT_MARGIN, mode.minimum_margin_fraction)
    price = Decimal(str(price))
    if not price.is_finite() or price <= 0:
        return {'passes': False, 'minimum_margin_fraction': str(minimum_margin)}
    fixed = landed + sum(mode.costs.model_dump().values(), Decimal(0))
    net, charges, cost, profit = _economics(policy, fixed, price)
    return {'passes': net > 0 and profit >= net * minimum_margin and profit >= mode.minimum_contribution_gbp,
        'minimum_margin_fraction': str(minimum_margin),
        'margin_fraction': str(profit / net) if net > 0 else None,
        'profit_gbp': str(profit), 'total_cost_gbp': str(cost),
        'net_revenue_gbp': str(net), 'fixed_cost_gbp': str(fixed),
        'charges_gbp': {key: str(value) for key, value in charges.items()}}
