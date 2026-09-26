from decimal import Decimal as D
from datetime import datetime, timezone

from app.services.commerce_pricing import (
    Condition, ConditionPolicy, CostStack, FulfilmentMode, MarketEvidence,
    SupplierOffer, condition_allowed, eligible_offers, evaluate_price,
)


def test_condition_requires_explicit_consent():
    assert not condition_allowed(ConditionPolicy.USED_ALLOWED, Condition.USED, False)
    assert not condition_allowed(ConditionPolicy.NEW_ONLY, Condition.REFURBISHED, True)
    assert condition_allowed(ConditionPolicy.NEW_OR_REFURBISHED, Condition.REFURBISHED, True)


def test_priority_restricts_suppliers_stock_capacity_and_delivery():
    now = datetime(2026, 9, 26, tzinfo=timezone.utc)
    offers = [
        SupplierOffer("Amazon", "retail", Condition.NEW, D("300"), D("0"), D("0"), D("2"), "2026-09-26", True, True, 1),
        SupplierOffer("eBay", "marketplace", Condition.NEW, D("250"), D("0"), D("0"), D("5"), "2026-09-26", True, True, 1),
        SupplierOffer("Overclockers UK", "retail", Condition.NEW, D("290"), D("5"), D("0"), D("1"), "2026-09-26", True, True, 3),
    ]
    assert eligible_offers(offers, FulfilmentMode.PRIORITY, ConditionPolicy.NEW_ONLY, False, now=now) == []
    result = eligible_offers(offers, FulfilmentMode.PRIORITY, ConditionPolicy.NEW_ONLY, False, priority_capacity=True, now=now)
    assert [offer.supplier for offer in result] == ["Amazon"]
    standard = eligible_offers(offers, FulfilmentMode.STANDARD, ConditionPolicy.NEW_ONLY, False, now=now)
    assert all(offer.channel == "retail" for offer in standard)


def test_true_cost_and_sold_market_gate_ignore_active_asking_price():
    costs = CostStack(D("800"), D("90"), D("15"), D("25"), D("30"), D("35"), D("20"), D("15"), D("40"))
    market = MarketEvidence(Condition.NEW, D("1200"), 6, "2026-09-26", active_median_gbp=D("2000"))
    result = evaluate_price(costs, market, Condition.NEW, D("100"), D("0.15"), now=datetime(2026, 9, 26, tzinfo=timezone.utc))
    assert result.offerable
    assert result.price_gbp == D("1258.82")


def test_market_gate_suppresses_uneconomic_build():
    costs = CostStack(D("1000"), D("100"), D("20"), D("30"), D("30"), D("30"), D("20"), D("20"), D("50"))
    market = MarketEvidence(Condition.NEW, D("1000"), 10, "2026-09-26", active_median_gbp=D("2000"))
    result = evaluate_price(costs, market, Condition.NEW, D("100"), D("0.20"), now=datetime(2026, 9, 26, tzinfo=timezone.utc))
    assert not result.offerable
    assert result.price_gbp is None


def test_stale_sold_evidence_cannot_authorise_a_quote():
    costs = CostStack(D("500"), D("80"), D("10"), D("20"), D("20"), D("20"), D("10"), D("10"), D("30"))
    market = MarketEvidence(Condition.NEW, D("1500"), 10, "2026-07-01")
    result = evaluate_price(costs, market, Condition.NEW, D("100"), D("0.15"), now=datetime(2026, 9, 26, tzinfo=timezone.utc))
    assert not result.offerable
